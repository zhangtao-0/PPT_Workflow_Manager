"""配置系统（ADR-002）。

职责：
1. 分层覆盖：Built-in Defaults → defaults.yaml → config.yaml
   → project.yaml → project_overrides.yaml → Task Runtime → CLI args（越靠后优先级越高）。
2. Governance 校验：Effective Config 生成后执行约束校验，
   违反 HARD 约束的配置即使 merge 成功也必须被拒绝。
3. 三档规则：HARD（不可覆盖）/ PROJECT（项目可覆盖）/ RUNTIME（单任务可覆盖）。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# 三档规则定义
# ---------------------------------------------------------------------------

TIER_HARD = "hard"
TIER_PROJECT = "project"
TIER_RUNTIME = "runtime"


@dataclass(frozen=True)
class ParamRule:
    """一条参数的三档规则声明。"""

    path: str           # 点分路径，如 "retry.max_attempts"
    tier: str           # hard / project / runtime
    description: str = ""


# 内置三档规则表（V1 基线，见 ADR-002 示例映射）
BUILTIN_PARAM_RULES: dict[str, ParamRule] = {
    # HARD —— 不可覆盖
    "governance.object_id_unique": ParamRule("governance.object_id_unique", TIER_HARD, "Object ID 唯一"),
    "governance.stage_07B.no_renumber": ParamRule("governance.stage_07B.no_renumber", TIER_HARD, "07B 不重新编号"),
    "governance.stage_07B.allow_multiple_objects": ParamRule(
        "governance.stage_07B.allow_multiple_objects", TIER_HARD, "07B 一次只允许一个正式对象"
    ),
    # PROJECT —— 项目可覆盖
    "retry.max_attempts": ParamRule("retry.max_attempts", TIER_PROJECT, "最大重试次数"),
    "retry.transport": ParamRule("retry.transport", TIER_PROJECT, "传输重试次数"),
    "retry.quality": ParamRule("retry.quality", TIER_PROJECT, "质量重试次数"),
    "chatgpt.conversation_mode": ParamRule("chatgpt.conversation_mode", TIER_PROJECT, "对话模式"),
    "download.output_dir": ParamRule("download.output_dir", TIER_PROJECT, "下载目录"),
    # RUNTIME —— 单任务可覆盖
    "task.timeout": ParamRule("task.timeout", TIER_RUNTIME, "当前 Task timeout"),
    "debug": ParamRule("debug", TIER_RUNTIME, "debug 开关"),
    "dry_run": ParamRule("dry_run", TIER_RUNTIME, "dry-run 开关"),
}


# ---------------------------------------------------------------------------
# 分层合并
# ---------------------------------------------------------------------------

def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """递归合并：override 覆盖 base，返回新 dict，不修改入参。"""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# ---------------------------------------------------------------------------
# Governance 校验
# ---------------------------------------------------------------------------

def _get_path(data: dict[str, Any], dotted: str) -> Any:
    """按点分路径取值，不存在返回 None。"""
    node: Any = data
    for part in dotted.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def _set_path(data: dict[str, Any], dotted: str, value: Any) -> None:
    """按点分路径写值，中间节点自动创建 dict。"""
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


class GovernanceViolation(Exception):
    """配置违反治理 HARD 约束。"""

    def __init__(self, path: str, description: str, value: Any) -> None:
        self.path = path
        self.description = description
        self.value = value
        super().__init__(f"Governance HARD 约束被违反：{path}（{description}）")


def _iter_paths(data: dict[str, Any], prefix: str = "") -> list[str]:
    """展开 dict 为点分路径列表。"""
    paths: list[str] = []
    for key, value in data.items():
        full = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            paths.extend(_iter_paths(value, full))
        else:
            paths.append(full)
    return paths


@dataclass
class EffectiveConfig:
    """合并后的最终配置，附带来源与校验结果。"""

    data: dict[str, Any]
    # 每个参数点分路径 → 覆盖来源层级（用于追溯）
    provenance: dict[str, str] = field(default_factory=dict)
    violations: list[GovernanceViolation] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.violations

    def get(self, dotted: str, default: Any = None) -> Any:
        v = _get_path(self.data, dotted)
        return default if v is None else v


class ConfigLoader:
    """按 ADR-002 的分层顺序加载并校验配置。"""

    def __init__(
        self,
        defaults_path: Path | None = None,
        param_rules: dict[str, ParamRule] | None = None,
    ) -> None:
        self.defaults_path = defaults_path
        self.param_rules = param_rules or BUILTIN_PARAM_RULES

    # -- 分层加载 ---------------------------------------------------------
    def load_effective(
        self,
        config_yaml: dict[str, Any] | None = None,
        project_yaml: dict[str, Any] | None = None,
        project_overrides: dict[str, Any] | None = None,
        runtime_overrides: dict[str, Any] | None = None,
        cli_overrides: dict[str, Any] | None = None,
    ) -> EffectiveConfig:
        """按顺序 merge 各层，返回 EffectiveConfig（含 provenance 与校验）。"""
        layers: list[tuple[str, dict[str, Any]]] = []
        layers.append(("builtin", self._builtin_defaults()))
        layers.append(("defaults", self._load_yaml(self.defaults_path)))

        effective: dict[str, Any] = {}
        provenance: dict[str, str] = {}

        for name, layer in layers:
            for p in _iter_paths(layer):
                provenance[p] = name
            effective = deep_merge(effective, layer)

        for name, layer in [
            ("config", config_yaml),
            ("project", project_yaml),
            ("project_overrides", project_overrides),
            ("runtime", runtime_overrides),
            ("cli", cli_overrides),
        ]:
            if not layer:
                continue
            for p in _iter_paths(layer):
                provenance[p] = name
            effective = deep_merge(effective, layer)

        violations = self._validate_governance(effective, provenance)
        return EffectiveConfig(data=effective, provenance=provenance, violations=violations)

    # -- 内置默认 ---------------------------------------------------------
    def _builtin_defaults(self) -> dict[str, Any]:
        return {
            "queue": {"concurrency": 1},
            "retry": {"transport": 3, "quality": 2, "max_attempts": 2},
            "governance": {
                "object_id_unique": True,
                "stage_07B": {"no_renumber": True, "allow_multiple_objects": False},
            },
            "debug": False,
            "dry_run": False,
        }

    def _load_yaml(self, path: Path | None) -> dict[str, Any]:
        if path is None or not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    # -- Governance 校验 --------------------------------------------------
    def _validate_governance(
        self, effective: dict[str, Any], provenance: dict[str, str]
    ) -> list[GovernanceViolation]:
        violations: list[GovernanceViolation] = []
        for path, rule in self.param_rules.items():
            if rule.tier != TIER_HARD:
                continue
            value = _get_path(effective, path)
            # HARD 约束的预期值来自 builtin defaults，被覆盖即违规
            expected = _get_path(self._builtin_defaults(), path)
            if value is not None and expected is not None and value != expected:
                violations.append(GovernanceViolation(path, rule.description, value))
        return violations


# 便捷函数：提供参数三档声明，供后续 Stage Contract 校验复用
def tier_of(path: str, rules: dict[str, ParamRule] | None = None) -> str | None:
    rules = rules or BUILTIN_PARAM_RULES
    rule = rules.get(path)
    return rule.tier if rule else None


__all__ = [
    "ConfigLoader",
    "EffectiveConfig",
    "GovernanceViolation",
    "ParamRule",
    "BUILTIN_PARAM_RULES",
    "deep_merge",
    "tier_of",
    "TIER_HARD",
    "TIER_PROJECT",
    "TIER_RUNTIME",
]
