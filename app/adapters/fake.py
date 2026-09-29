"""FakeAdapter（A10）。

Phase A 的假执行器：不访问网页，模拟「Stage 00 → 07B」全链路中的 AI 执行环节。

行为由脚本控制（`script: dict[task_id, behavior]`），behavior ∈：
- "ok"        → 成功，生成假 artifact 文件，返回 ok=True
- "transport" → 传输类失败（可重试），返回 retryable=True
- "quality"   → 质量类失败（可重试），返回 retryable=True
- "blocked"   → 阻塞，返回 ok=False（不可重试）
- "rollback"  → 底层缺陷，返回 rollback=True

用途：Phase A 验收（设计方案 §22 Phase A 验收）——
用 FakeAdapter 跑通 Input→Stage→Task→Queue→FakeAdapter→Fake Artifact→Registry
→Gate→Success，以及 失败→Retry、Gate Fail→Rollback→Selective Rebuild，
全程不连接真实 ChatGPT。
"""

from __future__ import annotations

from pathlib import Path

from app.workflow.models import Task
from app.workflow.worker import ExecutionResult, Executor

# 1x1 透明 PNG，作为假 artifact 文件内容
_FAKE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f"
    b"\x00\x00\x05\x00\x01\x8f\x0e\xfc\x0a\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FakeAdapter(Executor):
    """Phase A 假执行器。"""

    def __init__(
        self,
        output_dir: str | Path | None = None,
        script: dict[str, str] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir else None
        self.script = script or {}
        self.calls: list[str] = []  # 记录被执行的 task_id（含重试）
        self.generated: dict[str, Path] = {}  # object_id -> 生成的文件路径

    def execute(self, task: Task) -> ExecutionResult:
        self.calls.append(task.task_id)
        behavior = self.script.get(task.task_id, "ok")

        if behavior == "ok":
            path = self._make_artifact(task)
            return ExecutionResult(ok=True)

        if behavior in ("transport", "quality"):
            kind = "transport" if behavior == "transport" else "quality"
            return ExecutionResult(ok=False, retryable=True, error=f"fake {kind} failure")

        if behavior == "blocked":
            return ExecutionResult(ok=False, retryable=False, error="fake blocked")

        if behavior == "rollback":
            return ExecutionResult(ok=False, rollback=True, error="fake underlying defect")

        return ExecutionResult(ok=False, retryable=False, error=f"unknown behavior: {behavior}")

    def _make_artifact(self, task: Task) -> Path | None:
        if self.output_dir is None:
            return None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # 一个 Object = 一个独立文件（设计 §26 基线 5）
        filename = f"{task.object_id or task.task_id}.png"
        path = self.output_dir / filename
        path.write_bytes(_FAKE_PNG)
        if task.object_id:
            self.generated[task.object_id] = path
        return path


__all__ = ["FakeAdapter"]
