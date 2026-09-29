"""Stage Definition Loader（A6）。

加载 `governance/stages/*.yaml`，解析为 StageDefinition 模型。
引擎只读取配置，不硬编码任何 Stage 流程（对齐设计方案 §14）。

Stage YAML 结构（以 07B 为例）见 governance/stages/07B.yaml。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Prerequisite(BaseModel):
    stage: str
    gate: str = "passed"


class QueueConfig(BaseModel):
    ordering: str = "sequence_asc"
    concurrency: int = 1


class StageInputs(BaseModel):
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class StageOutputs(BaseModel):
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)


class RetryConfig(BaseModel):
    transport: int = 3
    quality: int = 2


class StageDefinition(BaseModel):
    """机器可读的 Stage 定义。"""

    id: str
    name: str = ""
    prerequisites: list[Prerequisite] = Field(default_factory=list)
    executor: str = ""
    scope: str = "project"  # project | page | object
    queue: QueueConfig = Field(default_factory=QueueConfig)
    inputs: StageInputs = Field(default_factory=StageInputs)
    outputs: StageOutputs = Field(default_factory=StageOutputs)
    validators: list[str] = Field(default_factory=list)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    rollback: dict[str, Any] = Field(default_factory=dict)
    on_page_complete: list[str] = Field(default_factory=list)

    @property
    def prerequisite_stage_ids(self) -> list[str]:
        return [p.stage for p in self.prerequisites]


class StageLoader:
    """扫描目录，加载所有 Stage YAML。"""

    def __init__(self, stages_dir: str | Path) -> None:
        self.stages_dir = Path(stages_dir)
        self._defs: dict[str, StageDefinition] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.stages_dir.exists():
            return
        for path in sorted(self.stages_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not data.get("id"):
                # 文件名兜底：07B.yaml → 07B
                data["id"] = path.stem
            self._defs[data["id"]] = StageDefinition.model_validate(data)

    def get(self, stage_id: str) -> StageDefinition:
        if stage_id not in self._defs:
            raise KeyError(f"Stage 定义不存在：{stage_id}")
        return self._defs[stage_id]

    def all(self) -> list[StageDefinition]:
        return sorted(self._defs.values(), key=lambda d: d.id)

    def has(self, stage_id: str) -> bool:
        return stage_id in self._defs

    def __len__(self) -> int:
        return len(self._defs)


__all__ = [
    "StageLoader",
    "StageDefinition",
    "Prerequisite",
    "QueueConfig",
    "StageInputs",
    "StageOutputs",
    "RetryConfig",
]
