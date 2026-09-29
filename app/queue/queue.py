"""Task Queue（A7，第一部分）。

基于 A3 的 WorkflowDB，提供队列语义：
- enqueue：任务入队（状态置 READY）
- claim / complete / fail 等状态流转
- 优先级常量（对齐设计方案 §9.2）

状态机（§4.6）：
PENDING → READY → RUNNING → WAITING_REMOTE → COLLECTING → VALIDATING → COMPLETED
异常分支：RETRYABLE_FAILED / BLOCKED / ROLLBACK_REQUIRED / CANCELLED
"""

from __future__ import annotations

from typing import Any

from app.registry.db import WorkflowDB
from app.workflow.models import Task, TaskState

# 优先级常量（§9.2：P0 修复 > Gate Block > 当前 Stage > 后续预生成）
PRIORITY_P0_FIX = 1000
PRIORITY_GATE_BLOCK = 900
PRIORITY_CURRENT_STAGE = 100
PRIORITY_PREFETCH = 50


class TaskQueue:
    """对 WorkflowDB 的队列层封装。"""

    def __init__(self, db: WorkflowDB) -> None:
        self.db = db

    # -- 入队 -------------------------------------------------------------
    def enqueue(self, task: Task) -> None:
        """任务入队，状态置 READY。"""
        task.status = TaskState.READY
        self.db.upsert_task(task)

    def enqueue_many(self, tasks: list[Task]) -> None:
        for t in tasks:
            self.enqueue(t)

    # -- 领取 / 状态流转 --------------------------------------------------
    def claim_next(self, stage_id: str | None = None) -> str | None:
        return self.db.claim_next(stage_id)

    def get(self, task_id: str) -> Task:
        raw = self.db.get_task(task_id)
        if raw is None:
            raise KeyError(f"Task 不存在：{task_id}")
        return Task.model_validate(raw)

    def complete(self, task_id: str) -> None:
        self.db.set_task_status(task_id, TaskState.COMPLETED)

    def mark_retryable_failed(self, task_id: str, error: str) -> None:
        self.db.mark_retryable_failed(task_id, error)

    def mark_blocked(self, task_id: str, error: str) -> None:
        self.db.set_task_status(task_id, TaskState.BLOCKED, error)

    def mark_rollback_required(self, task_id: str, error: str) -> None:
        self.db.set_task_status(task_id, TaskState.ROLLBACK_REQUIRED, error)

    def cancel(self, task_id: str) -> None:
        self.db.set_task_status(task_id, TaskState.CANCELLED)

    def requeue(self, task_id: str) -> None:
        """把 retryable_failed 的任务重新置为 READY（供 retry/resume）。"""
        self.db.set_task_status(task_id, TaskState.READY)

    # -- 观察 -------------------------------------------------------------
    def status_summary(self) -> dict[str, int]:
        return self.db.count_by_status()

    def current_running(self) -> str | None:
        """返回一个 running 中的任务 id（若无则 None）。"""
        rows = self.db.list_tasks(status=TaskState.RUNNING.value)
        return rows[0]["task_id"] if rows else None

    def list(self, status: TaskState | None = None) -> list[Task]:
        """列出任务，可选按状态过滤。"""
        raw = self.db.list_tasks(status=status.value if status else None)
        return [Task.model_validate(r) for r in raw]


__all__ = [
    "TaskQueue",
    "PRIORITY_P0_FIX",
    "PRIORITY_GATE_BLOCK",
    "PRIORITY_CURRENT_STAGE",
    "PRIORITY_PREFETCH",
]
