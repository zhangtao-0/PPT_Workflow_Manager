"""A8 Gate Validator 测试。"""

from __future__ import annotations

import pytest

from app.gates.validator import GateRunner, get_validator


@pytest.fixture
def runner():
    return GateRunner()


def test_file_exists(tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    assert get_validator("file_exists")({"path": str(f)}).passed
    assert not get_validator("file_exists")({"path": str(tmp_path / "nope.png")}).passed


def test_unique_id():
    assert get_validator("unique_id")({"ids": ["A", "B", "C"]}).passed
    assert not get_validator("unique_id")({"ids": ["A", "B", "A"]}).passed


def test_object_id_ascii():
    assert get_validator("object_id_ascii")({"object_id": "CHAR_S07_CRAB"}).passed
    assert not get_validator("object_id_ascii")({"object_id": "角色_螃蟹"}).passed


def test_shape_name_matches_object_id():
    ctx = {"shape_name": "CHAR_S07_CRAB", "object_id": "CHAR_S07_CRAB"}
    assert get_validator("shape_name_matches_object_id")(ctx).passed
    assert not get_validator("shape_name_matches_object_id")({"shape_name": "Shape1", "object_id": "CHAR_S07_CRAB"}).passed


def test_expected_count_match():
    assert get_validator("expected_count_match")({"expected": 26, "actual": 26}).passed
    assert not get_validator("expected_count_match")({"expected": 26, "actual": 25}).passed


def test_no_unresolved_p0_defect():
    assert get_validator("no_unresolved_p0_defect")({"defects": []}).passed
    ctx = {"defects": [{"severity": "P0", "status": "open"}]}
    assert not get_validator("no_unresolved_p0_defect")(ctx).passed
    ctx2 = {"defects": [{"severity": "P0", "status": "resolved"}]}
    assert get_validator("no_unresolved_p0_defect")(ctx2).passed


def test_no_full_slide_flatten_only():
    assert get_validator("no_full_slide_flatten_only")({"flatten_only": False}).passed
    assert not get_validator("no_full_slide_flatten_only")({"flatten_only": True}).passed


def test_gate_runner_pass(runner, tmp_path):
    f = tmp_path / "a.png"
    f.write_bytes(b"x")
    g = runner.run("GATE_1", "07B", ["file_exists", "object_id_ascii"],
                   {"path": str(f), "object_id": "ABC"})
    assert g.status.value == "pass"
    assert len(g.validators) == 2


def test_gate_runner_fail_collects_blocking(runner):
    g = runner.run("GATE_2", "07B", ["unique_id", "object_id_ascii"],
                   {"ids": ["A", "A"], "object_id": "角色"})
    assert g.status.value == "fail"
    assert set(g.blocking_reasons) == {"unique_id", "object_id_ascii"}


def test_unknown_validator_raises(runner):
    with pytest.raises(KeyError):
        runner.run("GATE_3", "07B", ["not_registered"])
