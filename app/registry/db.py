"""SQLite 运行时库（ADR-004）。

只负责事务型运行状态，绝不取代项目 Manifest（YAML/JSON 仍是领域事实源）。

承载内容：
- Queue        : tasks / task_runs
- Runtime State: task.status
- Retry        : task.attempt / last_error
- Lock         : task_locks（避免重启后重复领取）
- Execution History: task_runs
- Operational Index : kv_index（如「某 Object 最新 accepted Artifact」快速查询）

设计约束：
- 单机单进程，默认并发 1，但 Lock 仍必须存在以支持断点恢复语义。
- 删掉 db 不应导致项目文件失去语义，最多导致 Queue/Index 需 rebuild。
- 所有写入走事务；领取任务用原子 UPDATE ... WHERE status=... 抢占。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.workflow.models import Task, TaskRun, TaskState, utcnow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    stage_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    page_identity TEXT,
    object_id TEXT,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_transport_retry INTEGER NOT NULL DEFAULT 3,
    max_quality_retry INTEGER NOT NULL DEFAULT 2,
    idempotency_key TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON tasks(status, priority);

CREATE TABLE IF NOT EXISTS task_runs (
    task_run_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    state TEXT NOT NULL,
    adapter TEXT,
    conversation_ref TEXT,
    gate_result_id TEXT,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_task_runs_task ON task_runs(task_id);

CREATE TABLE IF NOT EXISTS task_locks (
    task_id TEXT PRIMARY KEY,
    locked_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv_index (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


class WorkflowDB:
    """一个项目一个 workflow.db（projects/<project>/runtime/workflow.db）。"""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False + 每线程独立连接，配合单进程多线程场景
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._local = threading.local()
        self._exec_script(_SCHEMA)

    # -- 底层 -------------------------------------------------------------
    def _conn_for_thread(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.path))
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _exec_script(self, script: str) -> None:
        conn = self._conn_for_thread()
        conn.executescript(script)
        conn.commit()

    # -- Queue：Task CRUD -------------------------------------------------
    def upsert_task(self, task: Task) -> None:
        conn = self._conn_for_thread()
        conn.execute(
            """
            INSERT INTO tasks (
                task_id, task_type, stage_id, project_id, page_identity, object_id,
                status, priority, attempt, max_transport_retry, max_quality_retry,
                idempotency_key, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(task_id) DO UPDATE SET
                status=excluded.status,
                priority=excluded.priority,
                attempt=excluded.attempt,
                updated_at=excluded.updated_at
            """,
            (
                task.task_id, task.task_type, task.stage_id, task.project_id,
                task.page_identity, task.object_id, task.status.value, task.priority,
                task.attempt, task.max_transport_retry, task.max_quality_retry,
                task.idempotency_key, _iso(utcnow()), _iso(utcnow()),
            ),
        )
        conn.commit()

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self._conn_for_thread().execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    def set_task_status(self, task_id: str, status: TaskState, error: str | None = None) -> None:
        conn = self._conn_for_thread()
        conn.execute(
            "UPDATE tasks SET status=?, updated_at=?, last_error=? WHERE task_id=?",
            (status.value, _iso(utcnow()), error, task_id),
        )
        conn.commit()

    # -- Lock：原子领取 ---------------------------------------------------
    def claim_next(self, stage_id: str | None = None) -> str | None:
        """原子领取一个 READY 任务（返回 task_id，无则 None）。

        通过 UPDATE ... WHERE status='ready' 抢占 + 写入 lock 实现：
        单进程下天然串行，多进程/重启后也不会重复领取已完成的任务。
        """
        conn = self._conn_for_thread()
        try:
            conn.execute("BEGIN IMMEDIATE")
            query = "SELECT task_id FROM tasks WHERE status='ready'"
            params: list[Any] = []
            if stage_id:
                query += " AND stage_id=?"
                params.append(stage_id)
            query += " ORDER BY priority DESC, task_id ASC LIMIT 1"
            row = conn.execute(query, params).fetchone()
            if row is None:
                conn.commit()
                return None
            task_id = row["task_id"]
            conn.execute(
                "UPDATE tasks SET status='running', updated_at=? WHERE task_id=?",
                (_iso(utcnow()), task_id),
            )
            conn.execute(
                "INSERT INTO task_locks(task_id, locked_at) VALUES(?,?)",
                (task_id, _iso(utcnow())),
            )
            conn.commit()
            return task_id
        except Exception:
            conn.rollback()
            raise

    def release_lock(self, task_id: str) -> None:
        conn = self._conn_for_thread()
        conn.execute("DELETE FROM task_locks WHERE task_id=?", (task_id,))
        conn.commit()

    def is_locked(self, task_id: str) -> bool:
        row = self._conn_for_thread().execute(
            "SELECT 1 FROM task_locks WHERE task_id=?", (task_id,)
        ).fetchone()
        return row is not None

    # -- Retry ------------------------------------------------------------
    def mark_retryable_failed(self, task_id: str, error: str) -> None:
        conn = self._conn_for_thread()
        conn.execute(
            """
            UPDATE tasks
            SET status='retryable_failed',
                attempt=attempt+1,
                updated_at=?,
                last_error=?
            WHERE task_id=?
            """,
            (_iso(utcnow()), error, task_id),
        )
        conn.commit()

    # -- Execution History：TaskRun --------------------------------------
    def add_task_run(self, run: TaskRun) -> None:
        conn = self._conn_for_thread()
        conn.execute(
            """
            INSERT INTO task_runs (
                task_run_id, task_id, attempt, started_at, finished_at,
                state, adapter, conversation_ref, gate_result_id, last_error
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run.task_run_id, run.task_id, run.attempt, _iso(run.started_at),
                _iso(run.finished_at), run.state.value, run.adapter,
                run.conversation_ref, run.gate_result_id, run.last_error,
            ),
        )
        conn.commit()

    def list_task_runs(self, task_id: str) -> list[dict[str, Any]]:
        rows = self._conn_for_thread().execute(
            "SELECT * FROM task_runs WHERE task_id=? ORDER BY attempt ASC", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Operational Index ------------------------------------------------
    def set_index(self, key: str, value: Any) -> None:
        conn = self._conn_for_thread()
        conn.execute(
            "INSERT INTO kv_index(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )
        conn.commit()

    def get_index(self, key: str) -> Any | None:
        row = self._conn_for_thread().execute(
            "SELECT value FROM kv_index WHERE key=?", (key,)
        ).fetchone()
        return json.loads(row["value"]) if row else None

    # -- 统计 -------------------------------------------------------------
    def count_by_status(self) -> dict[str, int]:
        rows = self._conn_for_thread().execute(
            "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        """列出任务（可按状态过滤）。"""
        conn = self._conn_for_thread()
        if status:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status=? ORDER BY priority DESC, task_id ASC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY priority DESC, task_id ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    # -- rebuild ----------------------------------------------------------
    def rebuild_index(self, facts: dict[str, Any]) -> None:
        """从 Manifest 重建 Operational Index 的占位实现。

        真实实现（Phase 后续）会扫描项目 artifact_manifest.json 重建
        「object → 最新 accepted Artifact」等索引。此处提供最小可运行契约。
        """
        conn = self._conn_for_thread()
        conn.execute("DELETE FROM kv_index")
        for key, value in facts.items():
            conn.execute(
                "INSERT INTO kv_index(key, value) VALUES(?,?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        conn.commit()

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
        self._conn.close()


__all__ = ["WorkflowDB"]
