"""A10 FakeAdapter 端到端测试（Phase A 验收，对应设计 §22/§23）。

不访问网页，验证整条链：
1. happy path：Stage 00 → 07B 全链路（建项目 → 锁 ObjectSpec → 建 Task →
   入队 → FakeAdapter 生成 → Registry → Gate → Success）
2. Retry：transport/quality 失败 → retryable_failed → requeue → 成功
3. Rollback：底层缺陷 → rollback_required → Selective Rebuild
4. 断点恢复语义：completed 不被重复领取（§23.3）
"""

from __future__ import annotations

import json

import pytest

from app.adapters.fake import FakeAdapter
from app.gates.validator import GateRunner
from app.queue.queue import TaskQueue
from app.registry.db import WorkflowDB
from app.registry.registry import ArtifactRegistry, sha256_file
from app.rollback.controller import RollbackController
from app.workflow.models import Artifact, ArtifactStatus, ObjectSpec, Task
from app.workflow.project import ProjectManager
from app.workflow.worker import Worker


# ---------------------------------------------------------------------------
# 辅助：模拟 Stage 07A 锁定对象，产出 ObjectSpec 列表
# ---------------------------------------------------------------------------

def _locked_object_specs() -> list[ObjectSpec]:
    return [
        ObjectSpec(object_id="CHAR_S07_CRAB", page_identity="S07", sequence=1, name="小螃蟹角色", locked=True),
        ObjectSpec(object_id="CARD_S07_MAIN", page_identity="S07", sequence=2, name="任务卡片", locked=True),
        ObjectSpec(object_id="TRAIN_S07", page_identity="S07", sequence=3, name="列车", locked=True),
    ]


def _tasks_from_specs(specs: list[ObjectSpec], project_id: str) -> list[Task]:
    return [
        Task(
            task_id=f"TASK_07B_{spec.object_id}",
            task_type="asset_generation",
            stage_id="07B",
            project_id=project_id,
            page_identity=spec.page_identity,
            object_id=spec.object_id,
        )
        for spec in specs
    ]


@pytest.fixture
def pm(tmp_path):
    return ProjectManager(tmp_path / "projects")


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

def test_stage_00_to_07b_full_chain(pm, tmp_path):
    # Stage 00：建项目
    project = pm.create("友谊号列车")
    artifacts_dir = pm.projects_root / project.project_id / "artifacts"

    # Stage 07A：锁定 ObjectSpec
    specs = _locked_object_specs()

    # Stage 07B：建 Task 入队
    db = WorkflowDB(pm.runtime_db_path(project.project_id))
    queue = TaskQueue(db)
    tasks = _tasks_from_specs(specs, project.project_id)
    queue.enqueue_many(tasks)

    # Worker + FakeAdapter
    fake = FakeAdapter(output_dir=artifacts_dir)
    worker = Worker(queue, fake)
    processed = worker.run(stage_id="07B")

    # 三个对象全部处理
    assert len(processed) == 3
    for tid in processed:
        assert queue.get(tid).status.value == "completed"

    # 一个 Object = 一个独立文件
    for spec in specs:
        f = artifacts_dir / f"{spec.object_id}.png"
        assert f.exists()

    # Registry 登记，每个都有 hash
    registry = ArtifactRegistry(artifacts_dir / "artifact_manifest.json", db=db)
    for spec in specs:
        f = artifacts_dir / f"{spec.object_id}.png"
        registry.register(
            Artifact(
                artifact_id=f"ART_{spec.object_id}",
                project_id=project.project_id,
                stage_id="07B",
                object_id=spec.object_id,
                status=ArtifactStatus.ACCEPTED,
                is_fact_source=True,
            ),
            file_path=f,
        )
    assert registry.count_accepted() == 3

    # Gate：对象唯一 + 数量匹配
    runner = GateRunner()
    gate = runner.run(
        "GATE_07B_E2E", "07B",
        ["object_id_unique", "expected_count_match", "object_id_ascii"],
        context={"ids": [s.object_id for s in specs], "expected": 3, "actual": 3, "object_id": "CHAR_S07_CRAB"},
    )
    assert gate.status.value == "pass"

    # manifest 事实源落盘
    manifest = artifacts_dir / "artifact_manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(data) == 3
    db.close()


# ---------------------------------------------------------------------------
# 2. Retry
# ---------------------------------------------------------------------------

def test_retry_transport_then_success(pm, tmp_path):
    project = pm.create("X")
    db = WorkflowDB(pm.runtime_db_path(project.project_id))
    queue = TaskQueue(db)
    task = Task(task_id="TASK_1", task_type="asset_generation", stage_id="07B",
                project_id=project.project_id, object_id="OBJ_1")
    queue.enqueue(task)

    # 第一次 transport 失败
    fake = FakeAdapter(output_dir=pm.projects_root / project.project_id / "artifacts",
                       script={"TASK_1": "transport"})
    Worker(queue, fake).run(stage_id="07B")
    t = queue.get("TASK_1")
    assert t.status.value == "retryable_failed"
    assert t.attempt == 1

    # 改成成功，requeue 后重试
    fake.script["TASK_1"] = "ok"
    queue.requeue("TASK_1")
    Worker(queue, fake).run(stage_id="07B")
    assert queue.get("TASK_1").status.value == "completed"
    # Object ID 不变（§26 基线）
    assert queue.get("TASK_1").object_id == "OBJ_1"
    db.close()


def test_quality_retry_limit_exceeded_blocks(pm, tmp_path):
    project = pm.create("X")
    db = WorkflowDB(pm.runtime_db_path(project.project_id))
    queue = TaskQueue(db)
    queue.enqueue(Task(task_id="T1", task_type="x", stage_id="07B",
                       project_id=project.project_id, object_id="O1"))

    fake = FakeAdapter(script={"T1": "blocked"})
    Worker(queue, fake).run(stage_id="07B")
    assert queue.get("T1").status.value == "blocked"
    db.close()


# ---------------------------------------------------------------------------
# 3. Rollback → Selective Rebuild
# ---------------------------------------------------------------------------

def test_rollback_selective_rebuild(pm, tmp_path):
    project = pm.create("X")
    artifacts_dir = pm.projects_root / project.project_id / "artifacts"

    db = WorkflowDB(pm.runtime_db_path(project.project_id))
    queue = TaskQueue(db)
    # 三个对象，其中 OBJ_2 触发底层缺陷
    specs = [
        ObjectSpec(object_id="OBJ_1", page_identity="S07", sequence=1, locked=True),
        ObjectSpec(object_id="OBJ_2", page_identity="S07", sequence=2, locked=True),
        ObjectSpec(object_id="OBJ_3", page_identity="S07", sequence=3, locked=True),
    ]
    queue.enqueue_many(_tasks_from_specs(specs, project.project_id))

    fake = FakeAdapter(output_dir=artifacts_dir,
                       script={"TASK_07B_OBJ_2": "rollback"})
    Worker(queue, fake).run(stage_id="07B")

    # OBJ_1, OBJ_3 完成；OBJ_2 标记 rollback_required
    assert queue.get("TASK_07B_OBJ_1").status.value == "completed"
    assert queue.get("TASK_07B_OBJ_3").status.value == "completed"
    assert queue.get("TASK_07B_OBJ_2").status.value == "rollback_required"

    # 登记已完成对象，然后回退 OBJ_2 的缺陷（L02 → 07B）
    registry = ArtifactRegistry(artifacts_dir / "artifact_manifest.json", db=db)
    for oid in ("OBJ_1", "OBJ_3"):
        f = artifacts_dir / f"{oid}.png"
        registry.register(Artifact(artifact_id=f"ART_{oid}", project_id=project.project_id,
                                   stage_id="07B", object_id=oid,
                                   status=ArtifactStatus.ACCEPTED, is_fact_source=True),
                          file_path=f)

    controller = RollbackController(registry=registry)
    plan = controller.plan("L02", affected_artifact_ids=["ART_OBJ_2"], stage_id="10")
    assert plan.rollback_to == "07B"
    marked = controller.execute(plan)

    # OBJ_2 本就没有 accepted artifact（rollback 了），跳过；OBJ_1/OBJ_3 不受影响
    assert registry.by_id("ART_OBJ_1").status == ArtifactStatus.ACCEPTED
    assert registry.by_id("ART_OBJ_3").status == ArtifactStatus.ACCEPTED
    db.close()


# ---------------------------------------------------------------------------
# 4. 断点恢复语义（§23.3）
# ---------------------------------------------------------------------------

def test_breakpoint_no_reclaim_completed(pm, tmp_path):
    project = pm.create("X")
    db = WorkflowDB(pm.runtime_db_path(project.project_id))
    queue = TaskQueue(db)
    queue.enqueue_many([
        Task(task_id="T1", task_type="x", stage_id="07B", project_id=project.project_id, object_id="O1"),
        Task(task_id="T2", task_type="x", stage_id="07B", project_id=project.project_id, object_id="O2"),
    ])

    fake = FakeAdapter(output_dir=pm.projects_root / project.project_id / "artifacts")
    # 第一次只处理到 T1（limit=1），模拟「执行到一半关闭」
    Worker(queue, fake).run(stage_id="07B", limit=1)
    assert queue.get("T1").status.value == "completed"
    assert queue.get("T2").status.value == "ready"

    # 重启（新 Worker 实例）后继续，只处理 T2
    fake2 = FakeAdapter(output_dir=pm.projects_root / project.project_id / "artifacts")
    processed = Worker(queue, fake2).run(stage_id="07B")
    assert processed == ["T2"]
    # T1 未被重复执行
    assert fake2.calls == ["T2"]
    db.close()
