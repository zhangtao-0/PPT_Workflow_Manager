"""A3 SQLite 运行时库测试。

覆盖：Task CRUD、原子领取（Lock）、断点恢复语义、重试、TaskRun 历史、
Operational Index、rebuild 契约、删除 db 不影响语义。
"""

from __future__ import annotations

import pytest

from app.registry.db import WorkflowDB
from app.workflow.models import Task, TaskRun, TaskState


@pytest.fixture
def db(tmp_path):
    d = WorkflowDB(tmp_path / "runtime" / "workflow.db")
    yield d
    d.close()


def _task(task_id: str, status: TaskState = TaskState.READY) -> Task:
    return Task(
        task_id=task_id, task_type="asset_generation", stage_id="07B",
        project_id="P1", object_id=f"OBJ_{task_id}", status=status,
    )


def test_upsert_and_get(db):
    db.upsert_task(_task("T1"))
    got = db.get_task("T1")
    assert got["task_id"] == "T1"
    assert got["status"] == "ready"


def test_upsert_updates_existing(db):
    db.upsert_task(_task("T1", TaskState.READY))
    db.upsert_task(_task("T1", TaskState.RUNNING))
    assert db.get_task("T1")["status"] == "running"


def test_claim_next_locks_and_moves_to_running(db):
    db.upsert_task(_task("T1"))
    db.upsert_task(_task("T2"))
    claimed = db.claim_next()
    assert claimed == "T1"  # 按 task_id 升序
    assert db.get_task("T1")["status"] == "running"
    assert db.is_locked("T1")
    # 再领取得到 T2，而不是重复 T1
    assert db.claim_next() == "T2"


def test_claim_next_returns_none_when_empty(db):
    assert db.claim_next() is None


def test_claim_next_skips_non_ready(db):
    db.upsert_task(_task("T1", TaskState.RUNNING))
    db.upsert_task(_task("T2", TaskState.READY))
    assert db.claim_next() == "T2"


def test_breakpoint_recovery_does_not_reclaim_completed(db):
    db.upsert_task(_task("T1", TaskState.COMPLETED))
    db.upsert_task(_task("T2", TaskState.READY))
    # 重启后（新 claim）不会重复领取已 completed 的 T1
    assert db.claim_next() == "T2"


def test_release_lock(db):
    db.upsert_task(_task("T1"))
    db.claim_next()
    assert db.is_locked("T1")
    db.release_lock("T1")
    assert not db.is_locked("T1")


def test_mark_retryable_failed_increments_attempt(db):
    db.upsert_task(_task("T1"))
    db.mark_retryable_failed("T1", "timeout")
    got = db.get_task("T1")
    assert got["status"] == "retryable_failed"
    assert got["attempt"] == 1
    assert got["last_error"] == "timeout"


def test_task_run_history(db):
    run = TaskRun(task_run_id="R1", task_id="T1", attempt=1, state=TaskState.COMPLETED)
    db.add_task_run(run)
    runs = db.list_task_runs("T1")
    assert len(runs) == 1
    assert runs[0]["state"] == "completed"


def test_operational_index(db):
    db.set_index("object:OBJ_1:latest", {"artifact_id": "ART_9"})
    assert db.get_index("object:OBJ_1:latest") == {"artifact_id": "ART_9"}
    db.set_index("object:OBJ_1:latest", {"artifact_id": "ART_10"})
    assert db.get_index("object:OBJ_1:latest") == {"artifact_id": "ART_10"}


def test_count_by_status(db):
    db.upsert_task(_task("T1", TaskState.READY))
    db.upsert_task(_task("T2", TaskState.RUNNING))
    db.upsert_task(_task("T3", TaskState.COMPLETED))
    counts = db.count_by_status()
    assert counts == {"ready": 1, "running": 1, "completed": 1}


def test_rebuild_index_replaces_all(db):
    db.set_index("old", 1)
    db.rebuild_index({"object:OBJ_1:latest": {"artifact_id": "ART_9"}})
    assert db.get_index("old") is None
    assert db.get_index("object:OBJ_1:latest") == {"artifact_id": "ART_9"}


def test_delete_db_does_not_touch_manifest(tmp_path):
    """删掉 db 不影响项目 Manifest 语义（ADR-004 核心约束）。"""
    manifest = tmp_path / "artifact_manifest.json"
    manifest.write_text('{"object": "OBJ_1", "artifact": "ART_9"}', encoding="utf-8")
    db_file = tmp_path / "runtime" / "workflow.db"
    d = WorkflowDB(db_file)
    d.set_index("x", 1)
    d.close()
    db_file.unlink()  # 删除 db
    # Manifest 仍在，语义完整
    assert manifest.exists()
    assert "ART_9" in manifest.read_text(encoding="utf-8")
