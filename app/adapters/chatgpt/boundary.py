"""Task Boundary 快照（C1，对齐设计方案 §10.4）。

图片/文件下载必须知道「本轮新增了什么」。每次任务发送前记录边界快照：
- assistant turn 数
- 当前可下载资源标识集合
- 当前图片资源集合
- conversation id
- 时间戳

完成后只收取 boundary 之后的新资源。这是 Phase C 的核心：区分「本轮新增」与「历史资源」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class BoundarySnapshot:
    """任务发送前/后的资源边界快照。"""

    conversation_id: str
    assistant_turn_count: int
    downloadables: frozenset[str] = frozenset()   # 可下载资源标识（URL/ID）
    image_ids: frozenset[str] = frozenset()        # 图片资源标识
    captured_at: datetime = field(default_factory=_now)

    @classmethod
    def capture(
        cls,
        conversation_id: str,
        assistant_turn_count: int,
        downloadables: set[str] | frozenset[str] | None = None,
        image_ids: set[str] | frozenset[str] | None = None,
    ) -> "BoundarySnapshot":
        return cls(
            conversation_id=conversation_id,
            assistant_turn_count=assistant_turn_count,
            downloadables=frozenset(downloadables or set()),
            image_ids=frozenset(image_ids or set()),
        )


@dataclass(frozen=True)
class BoundaryDiff:
    """前后快照的差异：本轮新增的资源。"""

    new_downloadables: frozenset[str]
    new_image_ids: frozenset[str]
    turn_delta: int

    @property
    def has_new(self) -> bool:
        return bool(self.new_downloadables or self.new_image_ids)


def diff_boundary(before: BoundarySnapshot, after: BoundarySnapshot) -> BoundaryDiff:
    """计算本轮新增资源：after 相对 before 的增量。

    若 conversation 变了（切了新对话），则 after 的所有资源都视为「新增」，
    因为历史资源不再属于当前 task boundary。
    """
    if before.conversation_id != after.conversation_id:
        return BoundaryDiff(
            new_downloadables=after.downloadables,
            new_image_ids=after.image_ids,
            turn_delta=after.assistant_turn_count,
        )
    return BoundaryDiff(
        new_downloadables=after.downloadables - before.downloadables,
        new_image_ids=after.image_ids - before.image_ids,
        turn_delta=after.assistant_turn_count - before.assistant_turn_count,
    )


__all__ = ["BoundarySnapshot", "BoundaryDiff", "diff_boundary"]
