"""Retry / Rollback 控制器（A9）。

Retry 与 Rollback 分离（设计方案 §2.8）：
- Retry：本阶段任务本身失败，重新执行当前任务（不改变 Object ID / 编号）。
- Rollback：发现输入基线错误或底层缺陷，退回上游 Stage 重建。

Rollback 采用 Selective Rebuild 语义（§6.6）：
1. 标记受影响 Artifact 为 superseded / invalidated；
2. 计算依赖图影响范围；
3. 保留不受影响页面/对象；
4. 创建新的上游 StageRun；
5. 重新执行必要下游任务。
—— 绝不默认全项目重跑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.registry.registry import ArtifactRegistry
from app.workflow.models import ArtifactStatus, StageRun, StageRunStatus, utcnow

# 缺陷代码 → 默认回退 Stage（设计方案附录 B）
DEFECT_ROLLBACK_ROUTES: dict[str, str | list[str]] = {
    "P01": "04",
    "P02": "04",
    "P03": "04",
    "L01": "07A",
    "L02": "07B",
    "L03": ["07A", "08"],
    "L04": "07A",
    "T01": ["07B", "08"],
    "A01": ["07A", "08"],
    "A02": "09",
    "N01": ["08", "09"],
}


def rollback_stage_for(defect_code: str) -> str | list[str]:
    """根据缺陷代码返回回退目标 Stage（未收录则 None，需人工判定）。"""
    return DEFECT_ROLLBACK_ROUTES.get(defect_code)


@dataclass
class RollbackPlan:
    """一次回退的计划：受影响 Artifact + 回退目标 + 是否新建上游 StageRun。"""

    rollback_to: str | list[str]
    affected_artifact_ids: list[str] = field(default_factory=list)
    new_stage_run: StageRun | None = None
    note: str = ""

    @property
    def targets(self) -> list[str]:
        return self.rollback_to if isinstance(self.rollback_to, list) else [self.rollback_to]


class RetryController:
    """重试控制：区分 transport / quality 重试（§6.5）。"""

    def __init__(self, max_transport: int = 3, max_quality: int = 2) -> None:
        self.max_transport = max_transport
        self.max_quality = max_quality

    def should_retry(
        self, error_kind: str, transport_retries: int, quality_retries: int
    ) -> bool:
        """判断是否允许再次重试。error_kind ∈ {transport, quality}。"""
        if error_kind == "transport":
            return transport_retries < self.max_transport
        if error_kind == "quality":
            return quality_retries < self.max_quality
        raise ValueError(f"未知错误类型：{error_kind}")


class RollbackController:
    """回退控制器：Selective Rebuild。"""

    def __init__(self, registry: ArtifactRegistry | None = None) -> None:
        self.registry = registry

    def plan(self, defect_code: str, affected_artifact_ids: list[str],
             stage_id: str) -> RollbackPlan:
        target = rollback_stage_for(defect_code)
        if target is None:
            raise ValueError(f"未收录的缺陷代码：{defect_code}，需人工判定回退目标")

        new_run = StageRun(
            stage_run_id=f"SR_{utcnow().strftime('%Y%m%d%H%M%S')}_{defect_code}",
            stage_id=target[0] if isinstance(target, list) else target,
            status=StageRunStatus.PENDING,
            attempt=1,
        )
        return RollbackPlan(
            rollback_to=target,
            affected_artifact_ids=affected_artifact_ids,
            new_stage_run=new_run,
            note=f"{defect_code} → 回退 {target}",
        )

    def execute(self, plan: RollbackPlan) -> list[str]:
        """执行回退：把受影响 Artifact 标记为 superseded（不删除、不覆盖）。

        返回实际被标记的 artifact_id 列表。
        """
        if self.registry is None:
            return []
        marked: list[str] = []
        for aid in plan.affected_artifact_ids:
            try:
                self.registry.supersede(aid, reason=f"rollback to {plan.targets}")
                marked.append(aid)
            except KeyError:
                # 未登记的 artifact 跳过，不阻断回退
                continue
        return marked


__all__ = [
    "RetryController",
    "RollbackController",
    "RollbackPlan",
    "rollback_stage_for",
    "DEFECT_ROLLBACK_ROUTES",
]
