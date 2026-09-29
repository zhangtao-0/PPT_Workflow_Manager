"""领域与运行时数据模型（对齐设计方案 §4，ADR-004 补充运行时模型）。

设计原则：
- 领域对象（Project / Page / ObjectSpec / Artifact / Defect ...）是可长期归档、
  可 Git diff、可交给 AI / Work 的事实，必须可 JSON/YAML 序列化。
- 运行时对象（TaskState / TaskRun）是短生命周期运行状态，主要落在 SQLite。
- 所有枚举值尽量贴近设计方案 §4 的原始取值，避免研发期二次翻译。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    """统一时间源（UTC，序列化时带时区）。"""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------

class ProjectMode(str, Enum):
    NEW_BUILD = "new_build"
    REPAIR = "repair"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class StageRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MappingStatus(str, Enum):
    MATCHED = "matched"
    ADDED = "added"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    SHIFTED = "shifted"


class PageStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class ArtifactStatus(str, Enum):
    GENERATED = "generated"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    MANUAL_REVIEW = "manual_review"


class TaskState(str, Enum):
    """任务状态机（设计方案 §4.6）。

    正常链路：PENDING → READY → RUNNING → WAITING_REMOTE → COLLECTING
              → VALIDATING → COMPLETED
    异常分支：RETRYABLE_FAILED / BLOCKED / ROLLBACK_REQUIRED / CANCELLED
    """

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING_REMOTE = "waiting_remote"
    COLLECTING = "collecting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    RETRYABLE_FAILED = "retryable_failed"
    BLOCKED = "blocked"
    ROLLBACK_REQUIRED = "rollback_required"
    CANCELLED = "cancelled"


class DefectSeverity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class DefectStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"


class RepairDecision(str, Enum):
    KEEP = "KEEP"
    PATCH = "PATCH"
    SELECTIVE_REBUILD = "SELECTIVE_REBUILD"
    FULL_PAGE_REBUILD = "FULL_PAGE_REBUILD"
    RESTORE_MISSING_PAGE = "RESTORE_MISSING_PAGE"
    DELETE_CANDIDATE = "DELETE_CANDIDATE"


# ---------------------------------------------------------------------------
# 领域模型
# ---------------------------------------------------------------------------

class Project(BaseModel):
    model_config = ConfigDict(extra="allow")

    project_id: str
    name: str
    project_type: str = "精品课"
    mode: ProjectMode = ProjectMode.NEW_BUILD
    current_stage: str = "00"
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    project_root: str = ""
    governance_version: str = "ppt-workflow-v1"


class StageRun(BaseModel):
    model_config = ConfigDict(extra="allow")

    stage_run_id: str
    stage_id: str
    status: StageRunStatus = StageRunStatus.PENDING
    input_snapshot_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    attempt: int = 1
    executor: str = "chatgpt"
    conversation_ref: str | None = None
    output_artifact_ids: list[str] = Field(default_factory=list)
    gate_result_id: str | None = None


class Page(BaseModel):
    model_config = ConfigDict(extra="allow")

    page_identity: str
    current_index: int
    original_index: int | None = None
    page_name: str = ""
    status: PageStatus = PageStatus.ACTIVE
    page_type: str = ""
    source_refs: list[str] = Field(default_factory=list)


class PageMapping(BaseModel):
    model_config = ConfigDict(extra="allow")

    current_index: int
    original_index: int | None = None
    page_identity: str
    mapping_status: MappingStatus = MappingStatus.MATCHED
    handling: str = "keep"
    notes: str = ""


class ObjectSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    object_id: str
    page_identity: str
    sequence: int
    name: str = ""
    object_type: str = ""
    include_scope: str = ""
    exclude_scope: str = ""
    transparent: bool = True
    animated: bool = True
    ppt_native: bool = False
    completion_requirement: str = ""
    z_order_group: str = ""
    locked: bool = True
    revision: int = 1


class Task(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_id: str
    task_type: str
    stage_id: str
    project_id: str
    page_identity: str | None = None
    object_id: str | None = None
    status: TaskState = TaskState.PENDING
    priority: int = 100
    attempt: int = 0
    max_transport_retry: int = 3
    max_quality_retry: int = 2
    input_artifact_ids: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    executor: str = "chatgpt_image"
    idempotency_key: str | None = None


class Artifact(BaseModel):
    model_config = ConfigDict(extra="allow")

    artifact_id: str
    project_id: str
    stage_id: str
    page_identity: str | None = None
    object_id: str | None = None
    artifact_type: str = ""
    path: str = ""
    sha256: str | None = None
    source_executor: str = "chatgpt"
    source_task_id: str | None = None
    revision: int = 1
    status: ArtifactStatus = ArtifactStatus.GENERATED
    is_fact_source: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class ArtifactRelation(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_artifact_id: str
    target_artifact_id: str
    relation: str  # derived / referenced_by / materialized_as / assembled_into


class Batch(BaseModel):
    model_config = ConfigDict(extra="allow")

    batch_id: str
    range: list[int] = Field(default_factory=list)
    object_ids: list[str] = Field(default_factory=list)
    status: str = "pending"
    zip_artifact_id: str | None = None


class GateResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    gate_result_id: str
    stage_id: str
    status: GateStatus = GateStatus.PASS
    validators: list[dict[str, Any]] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)


class Defect(BaseModel):
    model_config = ConfigDict(extra="allow")

    defect_id: str
    code: str
    severity: DefectSeverity = DefectSeverity.P1
    page_identity: str | None = None
    object_id: str | None = None
    description: str = ""
    rollback_stage: str = ""
    status: DefectStatus = DefectStatus.OPEN


class Revision(BaseModel):
    model_config = ConfigDict(extra="allow")

    revision_id: str
    entity_type: str
    entity_id: str
    from_revision: int
    to_revision: int
    reason: str = ""
    changed_fields: list[str] = Field(default_factory=list)
    approved_by: str = "workflow"


# ---------------------------------------------------------------------------
# 运行时模型（ADR-004，主要落 SQLite）
# ---------------------------------------------------------------------------

class TaskRun(BaseModel):
    """一次 Task 的实际执行记录（Execution History）。"""

    model_config = ConfigDict(extra="allow")

    task_run_id: str
    task_id: str
    attempt: int = 1
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    state: TaskState = TaskState.RUNNING
    adapter: str = ""
    conversation_ref: str | None = None
    download_event: dict[str, Any] | None = None
    gate_result_id: str | None = None
    last_error: str | None = None


class RetryState(BaseModel):
    """重试状态（Retry 表）。"""

    model_config = ConfigDict(extra="allow")

    task_id: str
    attempt: int = 0
    next_retry_at: datetime | None = None
    last_error: str | None = None
    transport_retries: int = 0
    quality_retries: int = 0


__all__ = [
    "Project",
    "StageRun",
    "Page",
    "PageMapping",
    "ObjectSpec",
    "Task",
    "Artifact",
    "ArtifactRelation",
    "Batch",
    "GateResult",
    "Defect",
    "Revision",
    "TaskRun",
    "RetryState",
    "ProjectMode",
    "ProjectStatus",
    "StageRunStatus",
    "MappingStatus",
    "PageStatus",
    "ArtifactStatus",
    "GateStatus",
    "TaskState",
    "DefectSeverity",
    "DefectStatus",
    "RepairDecision",
    "utcnow",
]
