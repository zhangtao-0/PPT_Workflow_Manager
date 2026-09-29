"""A2 配置系统测试。

覆盖：分层覆盖顺序、Governance HARD 约束校验、三档规则、CLI 覆盖最高优先。
"""

from __future__ import annotations

import pytest

from app.workflow.config import (
    BUILTIN_PARAM_RULES,
    ConfigLoader,
    GovernanceViolation,
    deep_merge,
    tier_of,
    TIER_HARD,
    TIER_PROJECT,
    TIER_RUNTIME,
)


def test_deep_merge_override():
    base = {"retry": {"max_attempts": 2, "transport": 3}, "debug": False}
    override = {"retry": {"max_attempts": 3}, "debug": True}
    merged = deep_merge(base, override)
    assert merged["retry"]["max_attempts"] == 3
    assert merged["retry"]["transport"] == 3  # 未覆盖的保留
    assert merged["debug"] is True
    # 不修改入参
    assert base["retry"]["max_attempts"] == 2


def test_layered_override_priority():
    loader = ConfigLoader()
    eff = loader.load_effective(
        config_yaml={"retry": {"max_attempts": 3}},
        project_overrides={"retry": {"max_attempts": 4}},
        cli_overrides={"retry": {"max_attempts": 5}},
    )
    assert eff.get("retry.max_attempts") == 5  # CLI 最高优先


def test_config_beats_defaults_project_beats_config():
    loader = ConfigLoader()
    eff = loader.load_effective(
        config_yaml={"retry": {"max_attempts": 3}},
        project_yaml={"retry": {"max_attempts": 4}},
    )
    assert eff.get("retry.max_attempts") == 4


def test_governance_hard_constraint_rejected():
    loader = ConfigLoader()
    eff = loader.load_effective(
        project_overrides={"governance": {"stage_07B": {"allow_multiple_objects": True}}}
    )
    assert not eff.valid
    assert any("allow_multiple_objects" in v.path for v in eff.violations)


def test_governance_hard_constraint_ok_when_unchanged():
    loader = ConfigLoader()
    eff = loader.load_effective()
    assert eff.valid
    assert eff.get("governance.stage_07B.allow_multiple_objects") is False


def test_retry_max_attempts_is_project_tier():
    assert tier_of("retry.max_attempts") == TIER_PROJECT
    assert tier_of("governance.stage_07B.allow_multiple_objects") == TIER_HARD
    assert tier_of("debug") == TIER_RUNTIME


def test_provenance_tracks_override_source():
    loader = ConfigLoader()
    eff = loader.load_effective(cli_overrides={"debug": True})
    assert eff.provenance["debug"] == "cli"
    assert eff.provenance["retry.max_attempts"] == "builtin"


def test_unknown_param_has_no_tier():
    assert tier_of("nonexistent.path") is None
