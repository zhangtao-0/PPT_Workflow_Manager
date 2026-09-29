"""A1 数据模型测试。

覆盖：模型可 JSON/YAML 序列化、枚举取值与设计方案 §4 一致、默认值正确。
"""

from __future__ import annotations

import json

import pytest
import yaml

from app.workflow.models import (
    Artifact,
    ArtifactStatus,
    Defect,
    DefectSeverity,
    GateResult,
    GateStatus,
    ObjectSpec,
    Page,
    Project,
    ProjectMode,
    Task,
    TaskState,
    utcnow,
)


def test_project_roundtrip_json():
    p = Project(project_id="PPT_2026_FRIENDSHIP_TRAIN", name="友谊号列车")
    d = json.loads(p.model_dump_json())
    assert d["project_id"] == "PPT_2026_FRIENDSHIP_TRAIN"
    assert d["name"] == "友谊号列车"
    assert d["mode"] == "new_build"
    assert d["governance_version"] == "ppt-workflow-v1"


def test_project_roundtrip_yaml():
    p = Project(project_id="X", name="Y", mode=ProjectMode.REPAIR)
    text = yaml.safe_dump(p.model_dump(mode="json"), allow_unicode=True)
    back = yaml.safe_load(text)
    assert back["mode"] == "repair"


def test_object_spec_fields_match_design():
    o = ObjectSpec(
        object_id="CHAR_MISSION_01_CRAB",
        page_identity="MISSION_01",
        sequence=3,
        name="小螃蟹角色",
        object_type="character",
        include_scope="完整角色主体及必要光效",
        exclude_scope="背景、对话框、标题",
        transparent=True,
        animated=True,
        ppt_native=False,
        completion_requirement="补全被卡片遮挡部分",
        z_order_group="character",
        locked=True,
        revision=1,
    )
    assert o.object_id == "CHAR_MISSION_01_CRAB"
    assert o.sequence == 3
    assert o.locked is True


def test_task_state_enum_values():
    # 对齐设计方案 §4.6 的状态机命名
    assert TaskState.PENDING.value == "pending"
    assert TaskState.READY.value == "ready"
    assert TaskState.RUNNING.value == "running"
    assert TaskState.COMPLETED.value == "completed"
    assert TaskState.ROLLBACK_REQUIRED.value == "rollback_required"


def test_artifact_default_status_generated():
    a = Artifact(artifact_id="ART_1", project_id="P", stage_id="07B")
    assert a.status == ArtifactStatus.GENERATED
    assert a.is_fact_source is False
    assert a.revision == 1


def test_defect_severity_and_rollback():
    d = Defect(
        defect_id="DEF_0012",
        code="L02",
        severity=DefectSeverity.P0,
        page_identity="MISSION_01",
        object_id="CHAR_MISSION_01_CRAB",
        description="人物周围残留原页面矩形背景",
        rollback_stage="07B",
    )
    assert d.severity.value == "P0"
    assert d.rollback_stage == "07B"


def test_gate_result_validators_shape():
    g = GateResult(
        gate_result_id="GATE_07A_MISSION_01_R1",
        stage_id="07A",
        status=GateStatus.MANUAL_REVIEW,
        validators=[{"id": "unique_object_id", "status": "pass"}],
        blocking_reasons=[],
    )
    assert g.status == GateStatus.MANUAL_REVIEW


def test_utcnow_is_timezone_aware():
    t = utcnow()
    assert t.tzinfo is not None
