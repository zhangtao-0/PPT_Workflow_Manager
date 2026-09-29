"""A4 Project Manager 测试。"""

from __future__ import annotations

import pytest

from app.workflow.models import ProjectMode
from app.workflow.project import (
    COMMON_DIRS,
    STAGE_07_SUBDIRS,
    STAGE_DIRS,
    ProjectManager,
    generate_project_id,
)


@pytest.fixture
def pm(tmp_path):
    return ProjectManager(tmp_path / "projects")


def test_create_generates_full_dir_structure(pm):
    p = pm.create("友谊号列车")
    root = pm.projects_root / p.project_id
    assert (root / "project.yaml").exists()
    assert (root / "project_overrides.yaml").exists()
    for d in STAGE_DIRS.values():
        assert (root / d).is_dir(), d
    for sub in STAGE_07_SUBDIRS:
        assert (root / STAGE_DIRS["07"] / sub).is_dir(), sub
    for d in COMMON_DIRS:
        assert (root / d).is_dir(), d


def test_create_writes_project_yaml_with_correct_fields(pm):
    p = pm.create("友谊号列车", mode=ProjectMode.NEW_BUILD)
    loaded = pm.load(p.project_id)
    assert loaded.name == "友谊号列车"
    assert loaded.mode == ProjectMode.NEW_BUILD
    assert loaded.current_stage == "00"
    assert loaded.project_root == str(pm.projects_root / p.project_id)


def test_project_id_unique_when_not_specified(pm):
    p1 = pm.create("项目A")
    p2 = pm.create("项目A")
    assert p1.project_id != p2.project_id


def test_project_id_prefix_format():
    pid = generate_project_id("友谊号列车")
    assert pid.startswith("PPT_")
    # 时间戳 + slug + HHMMSS
    assert len(pid.split("_")) >= 4


def test_load_missing_project_raises(pm):
    with pytest.raises(FileNotFoundError):
        pm.load("DOES_NOT_EXIST")


def test_exists(pm):
    p = pm.create("X")
    assert pm.exists(p.project_id)
    assert not pm.exists("NOPE")


def test_runtime_db_path(pm):
    p = pm.create("X")
    assert pm.runtime_db_path(p.project_id).name == "workflow.db"
    assert pm.runtime_db_path(p.project_id).parent.name == "runtime"


def test_create_with_explicit_project_id(pm):
    p = pm.create("X", project_id="PPT_CUSTOM_ID")
    assert p.project_id == "PPT_CUSTOM_ID"
    assert pm.exists("PPT_CUSTOM_ID")
