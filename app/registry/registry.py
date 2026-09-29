"""Artifact Registry（A5）。

职责（对齐设计方案 §11 + ADR-004）：
- 登记 Artifact，计算 sha256；
- 按 object_id 查询最新 accepted 版本；
- 版本化：accepted / superseded / rejected，supersede 不覆盖旧文件；
- 去重：相同 hash 不重复登记；
- 文件 Manifest（artifact_manifest.json）为事实源，SQLite 为查询索引。

事实源优先级（§11.1）：accepted 07B image > object meta > final_asset_manifest
> 07A ObjectSpec > decomposition index > Stage 06 visual。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.registry.db import WorkflowDB
from app.workflow.models import Artifact, ArtifactStatus, utcnow

MANIFEST_FILENAME = "artifact_manifest.json"


def sha256_file(path: str | Path) -> str:
    """计算文件 sha256（分块读取，适合大文件）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class ArtifactRegistry:
    """单个项目的 Artifact 索引。

    manifest_path 默认 `<project_root>/artifacts/artifact_manifest.json`。
    db 可选传入，用于把「object → 最新 accepted」写入 SQLite 快速索引。
    """

    def __init__(self, manifest_path: str | Path, db: WorkflowDB | None = None) -> None:
        self.manifest_path = Path(manifest_path)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = db
        self._records: list[dict[str, Any]] = self._load()

    # -- 持久化 -----------------------------------------------------------
    def _load(self) -> list[dict[str, Any]]:
        if self.manifest_path.exists():
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        return []

    def _save(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self._records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # -- 登记 -------------------------------------------------------------
    def register(self, artifact: Artifact, file_path: str | Path | None = None) -> Artifact:
        """登记 Artifact。若给定 file_path 则计算并回填 sha256。

        去重：同 object_id + 同 sha256 已存在 accepted 时不重复追加。
        """
        if file_path and Path(file_path).exists():
            artifact.sha256 = sha256_file(file_path)

        # 去重（仅当有真实 sha256 时才判定，避免 None 误判为重复）
        if artifact.sha256 is not None:
            for rec in self._records:
                if (
                    rec.get("object_id") == artifact.object_id
                    and rec.get("sha256") == artifact.sha256
                    and rec.get("status") == ArtifactStatus.ACCEPTED.value
                ):
                    return Artifact.model_validate(rec)

        artifact.status = artifact.status or ArtifactStatus.ACCEPTED
        artifact.created_at = artifact.created_at or utcnow()
        self._records.append(artifact.model_dump(mode="json"))
        self._save()
        self._index_latest(artifact)
        return artifact

    def _index_latest(self, artifact: Artifact) -> None:
        if self.db and artifact.object_id:
            self.db.set_index(
                f"object:{artifact.object_id}:latest",
                {"artifact_id": artifact.artifact_id, "sha256": artifact.sha256,
                 "status": artifact.status.value},
            )

    # -- 查询 -------------------------------------------------------------
    def latest_accepted(self, object_id: str) -> Artifact | None:
        """返回 object_id 最新的 accepted Artifact（按 revision 取最大）。"""
        candidates = [
            Artifact.model_validate(r)
            for r in self._records
            if r.get("object_id") == object_id
            and r.get("status") == ArtifactStatus.ACCEPTED.value
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda a: a.revision)

    def by_id(self, artifact_id: str) -> Artifact | None:
        for r in self._records:
            if r.get("artifact_id") == artifact_id:
                return Artifact.model_validate(r)
        return None

    # -- 版本化 -----------------------------------------------------------
    def supersede(self, artifact_id: str, reason: str = "") -> None:
        """把指定 Artifact 标记为 superseded，不删除记录、不覆盖旧文件（§11.2）。"""
        for r in self._records:
            if r.get("artifact_id") == artifact_id:
                r["status"] = ArtifactStatus.SUPERSEDED.value
                if reason:
                    r["superseded_reason"] = reason
                self._save()
                return
        raise KeyError(f"Artifact 不存在：{artifact_id}")

    def reject(self, artifact_id: str, reason: str = "") -> None:
        for r in self._records:
            if r.get("artifact_id") == artifact_id:
                r["status"] = ArtifactStatus.REJECTED.value
                if reason:
                    r["reject_reason"] = reason
                self._save()
                return
        raise KeyError(f"Artifact 不存在：{artifact_id}")

    # -- 统计 -------------------------------------------------------------
    def count(self) -> int:
        return len(self._records)

    def count_accepted(self) -> int:
        return sum(1 for r in self._records if r.get("status") == ArtifactStatus.ACCEPTED.value)


__all__ = ["ArtifactRegistry", "sha256_file", "MANIFEST_FILENAME"]
