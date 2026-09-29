"""A9 Retry / Rollback 测试。"""

from __future__ import annotations

import pytest

from app.registry.registry import ArtifactRegistry
from app.rollback.controller import (
    RetryController,
    RollbackController,
    rollback_stage_for,
)
from app.workflow.models import Artifact, ArtifactStatus


def test_retry_transport_within_limit():
    c = RetryController(max_transport=3, max_quality=2)
    assert c.should_retry("transport", transport_retries=0, quality_retries=0)
    assert c.should_retry("transport", transport_retries=2, quality_retries=0)
    assert not c.should_retry("transport", transport_retries=3, quality_retries=0)


def test_retry_quality_within_limit():
    c = RetryController()
    assert c.should_retry("quality", transport_retries=0, quality_retries=0)
    assert c.should_retry("quality", transport_retries=0, quality_retries=1)
    assert not c.should_retry("quality", transport_retries=0, quality_retries=2)


def test_retry_unknown_kind_raises():
    c = RetryController()
    with pytest.raises(ValueError):
        c.should_retry("unknown", 0, 0)


def test_rollback_routes_known_codes():
    assert rollback_stage_for("L02") == "07B"
    assert rollback_stage_for("P01") == "04"
    assert rollback_stage_for("L03") == ["07A", "08"]
    assert rollback_stage_for("ZZZ") is None


def test_rollback_plan_creates_new_stage_run():
    c = RollbackController()
    plan = c.plan("L02", affected_artifact_ids=["ART_1", "ART_2"], stage_id="10")
    assert plan.rollback_to == "07B"
    assert plan.new_stage_run is not None
    assert plan.new_stage_run.stage_id == "07B"


def test_rollback_unknown_code_raises():
    c = RollbackController()
    with pytest.raises(ValueError):
        c.plan("UNKNOWN", [], "10")


def test_rollback_execute_supersedes(tmp_path):
    reg = ArtifactRegistry(tmp_path / "artifacts" / "artifact_manifest.json")
    reg.register(Artifact(artifact_id="ART_1", project_id="P", stage_id="07B",
                          object_id="OBJ_A", status=ArtifactStatus.ACCEPTED))
    reg.register(Artifact(artifact_id="ART_2", project_id="P", stage_id="07B",
                          object_id="OBJ_B", status=ArtifactStatus.ACCEPTED))

    c = RollbackController(registry=reg)
    plan = c.plan("L02", ["ART_1"], "10")
    marked = c.execute(plan)

    assert marked == ["ART_1"]
    assert reg.by_id("ART_1").status == ArtifactStatus.SUPERSEDED
    # 未受影响的不动
    assert reg.by_id("ART_2").status == ArtifactStatus.ACCEPTED
    # 记录仍在，不删除
    assert reg.count() == 2


def test_rollback_execute_skips_missing(tmp_path):
    reg = ArtifactRegistry(tmp_path / "artifacts" / "artifact_manifest.json")
    c = RollbackController(registry=reg)
    plan = c.plan("L02", ["NOPE"], "10")
    assert c.execute(plan) == []
