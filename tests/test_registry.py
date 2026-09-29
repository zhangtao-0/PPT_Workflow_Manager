"""A5 Artifact Registry 测试。"""

from __future__ import annotations

import pytest

from app.registry.db import WorkflowDB
from app.registry.registry import ArtifactRegistry, sha256_file
from app.workflow.models import Artifact, ArtifactStatus


@pytest.fixture
def registry(tmp_path):
    manifest = tmp_path / "artifacts" / "artifact_manifest.json"
    db = WorkflowDB(tmp_path / "runtime" / "workflow.db")
    reg = ArtifactRegistry(manifest, db=db)
    yield reg
    db.close()


def _artifact(aid, obj, rev=1):
    return Artifact(
        artifact_id=aid, project_id="P1", stage_id="07B",
        object_id=obj, revision=rev, status=ArtifactStatus.ACCEPTED,
    )


def test_register_and_latest_accepted(registry):
    registry.register(_artifact("ART_1", "OBJ_A", 1))
    registry.register(_artifact("ART_2", "OBJ_A", 2))
    latest = registry.latest_accepted("OBJ_A")
    assert latest.artifact_id == "ART_2"
    assert latest.revision == 2


def test_latest_accepted_none_when_missing(registry):
    assert registry.latest_accepted("NOPE") is None


def test_supersede_does_not_delete(registry):
    registry.register(_artifact("ART_1", "OBJ_A", 1))
    registry.supersede("ART_1", reason="重做")
    a = registry.by_id("ART_1")
    assert a.status == ArtifactStatus.SUPERSEDED
    # superseded 后不再是 accepted
    assert registry.latest_accepted("OBJ_A") is None
    assert registry.count() == 1  # 记录仍在


def test_supersede_missing_raises(registry):
    with pytest.raises(KeyError):
        registry.supersede("NOPE")


def test_reject(registry):
    registry.register(_artifact("ART_1", "OBJ_A", 1))
    registry.reject("ART_1", reason="透明背景失败")
    assert registry.by_id("ART_1").status == ArtifactStatus.REJECTED


def test_dedup_same_object_same_hash(registry, tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"hello")
    a1 = registry.register(_artifact("ART_1", "OBJ_A", 1), file_path=f)
    a2 = registry.register(_artifact("ART_2", "OBJ_A", 1), file_path=f)
    # 相同 hash 去重，返回已存在记录，不新增
    assert registry.count() == 1
    assert a1.artifact_id == a2.artifact_id


def test_sha256_is_stable(registry, tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"hello")
    assert sha256_file(f) == sha256_file(f)


def test_index_written_to_db(registry):
    registry.register(_artifact("ART_1", "OBJ_A", 1))
    idx = registry.db.get_index("object:OBJ_A:latest")
    assert idx["artifact_id"] == "ART_1"


def test_manifest_survives_reload(tmp_path):
    manifest = tmp_path / "artifacts" / "artifact_manifest.json"
    reg1 = ArtifactRegistry(manifest)
    reg1.register(_artifact("ART_1", "OBJ_A", 1))
    # 重新加载，从文件事实源恢复
    reg2 = ArtifactRegistry(manifest)
    assert reg2.latest_accepted("OBJ_A").artifact_id == "ART_1"
