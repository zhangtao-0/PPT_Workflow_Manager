"""Gate Validator（A8）。

通用 Validator 与 PPT 专用 Validator 的注册与执行（对齐设计方案 §15.1/15.2）。

三类 Gate（§6.4）：
- Machine Gate：程序直接判断（本模块实现）
- AI Gate：审查任务判断（V1 先由独立审查 Prompt 产出结构化结果，§15.3）
- Human Gate：人工确认

Validator 统一签名：`(context: dict) -> ValidatorResult`。
context 由调用方注入（如当前 Stage 的输出文件清单、Artifact 集合、page/object 数据）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.workflow.models import GateResult, GateStatus


@dataclass
class ValidatorResult:
    """单个 validator 的执行结果。"""

    id: str
    passed: bool
    detail: str = ""


ValidatorFunc = Callable[[dict[str, Any]], ValidatorResult]

_REGISTRY: dict[str, ValidatorFunc] = {}


def register(name: str) -> Callable[[ValidatorFunc], ValidatorFunc]:
    """装饰器：把 validator 注册进全局表。"""

    def decorator(fn: ValidatorFunc) -> ValidatorFunc:
        _REGISTRY[name] = fn
        return fn

    return decorator


def get_validator(name: str) -> ValidatorFunc:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(f"Validator 未注册：{name}") from None


# ---------------------------------------------------------------------------
# 通用 Validator（§15.1）
# ---------------------------------------------------------------------------

@register("file_exists")
def file_exists(ctx: dict[str, Any]) -> ValidatorResult:
    path = ctx.get("path")
    exists = bool(path) and Path(path).exists()
    return ValidatorResult("file_exists", exists, f"path={path}")


@register("hash_valid")
def hash_valid(ctx: dict[str, Any]) -> ValidatorResult:
    """检查 expected_sha256 与实际 sha256 一致（若提供）。"""
    expected = ctx.get("expected_sha256")
    actual = ctx.get("actual_sha256")
    if expected is None:
        return ValidatorResult("hash_valid", True, "no expected hash provided")
    ok = expected == actual
    return ValidatorResult("hash_valid", ok, f"expected={expected} actual={actual}")


@register("json_schema_valid")
def json_schema_valid(ctx: dict[str, Any]) -> ValidatorResult:
    """JSON 可解析且非空（V1 弱校验，强 schema 校验由 schemas/*.json 后续接入）。"""
    data = ctx.get("data")
    ok = isinstance(data, (dict, list)) and len(data) > 0
    return ValidatorResult("json_schema_valid", ok, "data non-empty")


@register("unique_id")
def unique_id(ctx: dict[str, Any]) -> ValidatorResult:
    ids = ctx.get("ids", [])
    ok = len(ids) == len(set(ids))
    return ValidatorResult("unique_id", ok, f"{len(ids)} ids, unique={ok}")


@register("all_dependencies_accepted")
def all_dependencies_accepted(ctx: dict[str, Any]) -> ValidatorResult:
    deps = ctx.get("dependencies", [])
    missing = [d for d in deps if d.get("status") != "accepted"]
    return ValidatorResult(
        "all_dependencies_accepted", not missing, f"missing={[m['id'] for m in missing]}"
    )


@register("expected_count_match")
def expected_count_match(ctx: dict[str, Any]) -> ValidatorResult:
    expected = ctx.get("expected")
    actual = ctx.get("actual")
    ok = expected is not None and expected == actual
    return ValidatorResult("expected_count_match", ok, f"expected={expected} actual={actual}")


@register("zip_contains_expected_files")
def zip_contains_expected_files(ctx: dict[str, Any]) -> ValidatorResult:
    entries = ctx.get("zip_entries", [])
    expected = ctx.get("expected_files", [])
    missing = [f for f in expected if f not in entries]
    return ValidatorResult("zip_contains_expected_files", not missing, f"missing={missing}")


# ---------------------------------------------------------------------------
# PPT 专用 Validator（§15.2）
# ---------------------------------------------------------------------------

@register("page_identity_unique")
def page_identity_unique(ctx: dict[str, Any]) -> ValidatorResult:
    return unique_id({**ctx, "ids": ctx.get("page_identities", [])})


@register("object_id_ascii")
def object_id_ascii(ctx: dict[str, Any]) -> ValidatorResult:
    obj_id = ctx.get("object_id", "")
    ok = bool(obj_id) and all(ord(c) < 128 for c in obj_id)
    return ValidatorResult("object_id_ascii", ok, f"object_id={obj_id}")


@register("object_id_unique")
def object_id_unique(ctx: dict[str, Any]) -> ValidatorResult:
    return unique_id({**ctx, "ids": ctx.get("object_ids", [])})


@register("shape_name_matches_object_id")
def shape_name_matches_object_id(ctx: dict[str, Any]) -> ValidatorResult:
    shape_name = ctx.get("shape_name")
    object_id = ctx.get("object_id")
    ok = bool(shape_name) and shape_name == object_id
    return ValidatorResult("shape_name_matches_object_id", ok, f"{shape_name} == {object_id}")


@register("no_full_slide_flatten_only")
def no_full_slide_flatten_only(ctx: dict[str, Any]) -> ValidatorResult:
    """禁止整页图片冒充正式 PPT（设计 §26 基线 9）。"""
    flattened = ctx.get("flatten_only", False)
    return ValidatorResult("no_full_slide_flatten_only", not flattened, f"flatten_only={flattened}")


@register("no_unresolved_p0_defect")
def no_unresolved_p0_defect(ctx: dict[str, Any]) -> ValidatorResult:
    defects = ctx.get("defects", [])
    p0_open = [d for d in defects if d.get("severity") == "P0" and d.get("status") == "open"]
    return ValidatorResult("no_unresolved_p0_defect", not p0_open, f"p0_open={len(p0_open)}")


# ---------------------------------------------------------------------------
# Gate 执行
# ---------------------------------------------------------------------------

@dataclass
class GateRunner:
    """按名字执行一组 validator，汇总为 GateResult。"""

    def run(self, gate_result_id: str, stage_id: str, validator_names: list[str],
            context: dict[str, Any] | None = None) -> GateResult:
        context = context or {}
        results: list[dict[str, Any]] = []
        blocking: list[str] = []
        for name in validator_names:
            fn = get_validator(name)
            r = fn(context)
            results.append({"id": r.id, "status": "pass" if r.passed else "fail", "detail": r.detail})
            if not r.passed:
                blocking.append(name)
        status = GateStatus.PASS if not blocking else GateStatus.FAIL
        return GateResult(
            gate_result_id=gate_result_id,
            stage_id=stage_id,
            status=status,
            validators=results,
            blocking_reasons=blocking,
        )


__all__ = [
    "GateRunner",
    "ValidatorResult",
    "register",
    "get_validator",
]
