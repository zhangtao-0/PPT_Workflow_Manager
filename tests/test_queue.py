"""A7 Task Queue + Worker 测试。"""

from __future__ import annotations

import pytest

from app.queue.queue import (
    PRIORITY_CURRENT_STAGE,
    PRIORITY_GATE_BLOCK,
    PRIORITY_P0_FIX,
    PRIORITY_PREFETCH,
    TaskQueue,
)
from app.registry.db import WorkflowDB
from app.workflow.models import Task, TaskState
from app.workflow.worker import ExecutionResult, Worker


@pytest.fixture
def db(tmp_path):
    d = WorkflowDB(tmp_path / "runtime" / "workflow.db")
    yield d
    d.close()


@pytest.fixture
def queue(db):
    return TaskQueue(db)


def _task(task_id, priority=PRIORITY_CURRENT_STAGE):
    return Task(
        task_id=task_id, task_type="asset_generation", stage_id="07B",
        project_id="P1", object_id=f"OBJ_{task_id}", priority=priority,
    )


class _Echo:
    def execute(self, task):
        return ExecutionResult(ok=True)


class _FailRetryable:
    def execute(self, task):
        return ExecutionResult(ok=False, retryable=True, error="timeout")


def test_enqueue_sets_ready(queue):
    queue.enqueue(_task("T1"))
    assert queue.get("T1").status == TaskState.READY


def test_worker_runs_until_empty(queue):
    queue.enqueue_many([_task("T1"), _task("T2"), _task("T3")])
    w = Worker(queue, _Echo())
    processed = w.run()
    assert processed == ["T1", "T2", "T3"]
    # 全部 completed
    for tid in processed:
        assert queue.get(tid).status == TaskState.COMPLETED


def test_worker_limit(queue):
    queue.enqueue_many([_task("T1"), _task("T2"), _task("T3")])
    w = Worker(queue, _Echo())
    processed = w.run(limit=2)
    assert len(processed) == 2


def test_worker_retryable_failed(queue):
    queue.enqueue(_task("T1"))
    w = Worker(queue, _FailRetryable())
    w.run()
    t = queue.get("T1")
    assert t.status == TaskState.RETRYABLE_FAILED
    assert t.attempt == 1


def test_priority_order(queue):
    # P0 修复 > Gate Block > 当前 Stage > 预生成
    queue.enqueue(_task("low", PRIORITY_PREFETCH))
    queue.enqueue(_task("normal", PRIORITY_CURRENT_STAGE))
    queue.enqueue(_task("gate", PRIORITY_GATE_BLOCK))
    queue.enqueue(_task("p0", PRIORITY_P0_FIX))
    w = Worker(queue, _Echo())
    processed = w.run()
    assert processed == ["p0", "gate", "normal", "low"]


def test_requeue_retryable(queue):
    queue.enqueue(_task("T1"))
    Worker(queue, _FailRetryable()).run()
    assert queue.get("T1").status == TaskState.RETRYABLE_FAILED
    queue.requeue("T1")
    assert queue.get("T1").status == TaskState.READY


def test_current_running(queue):
    assert queue.current_running() is None
    queue.enqueue(_task("T1"))
    queue.claim_next()
    assert queue.current_running() == "T1"


def test_status_summary(queue):
    queue.enqueue(_task("T1"))
    queue.enqueue(_task("T2"))
    summary = queue.status_summary()
    assert summary["ready"] == 2
