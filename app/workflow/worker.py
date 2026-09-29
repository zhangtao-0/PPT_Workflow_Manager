"""Worker（A7，第二部分）。

单进程常驻 Worker（ADR-001）：循环从队列领取 READY 任务，交给 Executor 执行，
根据结果流转状态（COMPLETED / RETRYABLE_FAILED / BLOCKED / ROLLBACK_REQUIRED）。

Executor 抽象与 A10 的 FakeAdapter 解耦：Worker 只关心「执行结果」三元组。
Phase A 严禁连接真实 ChatGPT——此处默认只接受注入的 Executor。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.queue.queue import TaskQueue
from app.workflow.models import Task, TaskState


@dataclass
class ExecutionResult:
    """一次执行的结果。"""

    ok: bool
    retryable: bool = False
    rollback: bool = False
    error: str | None = None


class Executor(Protocol):
    """执行器抽象。A10 的 FakeAdapter、B 阶段的 ChatGPTAdapter 都实现它。"""

    def execute(self, task: Task) -> ExecutionResult: ...


class Worker:
    """单进程 Worker：claim → execute → 状态流转。"""

    def __init__(self, queue: TaskQueue, executor: Executor) -> None:
        self.queue = queue
        self.executor = executor

    def run_once(self, stage_id: str | None = None) -> str | None:
        """处理一个任务，返回该 task_id；队列空返回 None。"""
        task_id = self.queue.claim_next(stage_id)
        if task_id is None:
            return None
        task = self.queue.get(task_id)
        result = self.executor.execute(task)

        if result.ok:
            self.queue.complete(task_id)
        elif result.rollback:
            self.queue.mark_rollback_required(task_id, result.error or "rollback required")
        elif result.retryable:
            self.queue.mark_retryable_failed(task_id, result.error or "retryable failure")
        else:
            self.queue.mark_blocked(task_id, result.error or "blocked")
        return task_id

    def run(self, stage_id: str | None = None, limit: int | None = None) -> list[str]:
        """循环消费直到队列空（或达到 limit），返回已处理的 task_id 列表。"""
        processed: list[str] = []
        while True:
            if limit is not None and len(processed) >= limit:
                break
            task_id = self.run_once(stage_id)
            if task_id is None:
                break
            processed.append(task_id)
        return processed


__all__ = ["Worker", "Executor", "ExecutionResult"]
