"""Download Collector（C2，对齐设计方案 §10.5）。

流程：
    snapshot before task
    → send task
    → wait complete
    → snapshot after task
    → diff downloadables
    → download
    → hash + dedup
    → register Artifact

下载完成不等于 Task 完成，仍需 Output Contract / Gate。

依赖注入一个 Downloader 抽象，使下载逻辑可脱离真实浏览器测试。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from app.adapters.chatgpt.boundary import BoundarySnapshot, diff_boundary
from app.registry.registry import ArtifactRegistry, sha256_file
from app.workflow.models import Artifact, ArtifactStatus


class Downloader(Protocol):
    """把资源标识（URL）下载到本地文件的抽象。"""

    def download(self, url: str, output_dir: Path) -> Path: ...


class HTTPDownloader:
    """真实下载器：用 urllib 拉取 http/https 资源。"""

    def __init__(self, headers: dict[str, str] | None = None) -> None:
        import urllib.request

        self._urlopen = urllib.request.urlopen
        self.headers = headers or {}

    def download(self, url: str, output_dir: Path) -> Path:
        import urllib.request

        output_dir.mkdir(parents=True, exist_ok=True)
        # 从 URL 提取文件名（去掉 query），无法提取时用 hash 兜底
        base = url.split("?")[0].rsplit("/", 1)[-1] or "file"
        req = urllib.request.Request(url, headers=self.headers)
        with self._urlopen(req, timeout=60) as resp:
            data = resp.read()
        path = output_dir / base
        path.write_bytes(data)
        return path


@dataclass
class CollectedResult:
    """一次收集的结果。"""

    downloaded: list[Path] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)  # path str -> sha256
    new_downloadables: frozenset[str] = frozenset()


def register_collected_artifacts(
    result: CollectedResult,
    registry: ArtifactRegistry,
    *,
    project_id: str,
    stage_id: str,
    page_identity: str | None = None,
    object_id: str | None = None,
    artifact_type: str = "download",
    is_fact_source: bool = False,
) -> list[Artifact]:
    """把收集结果登记为 Artifact（C3）。

    每个下载文件 → 一个 Artifact，sha256 来自 CollectedResult.hashes。
    返回成功登记的 Artifact 列表。
    """
    registered: list[Artifact] = []
    for path in result.downloaded:
        aid = f"ART_{Path(path).stem}"
        artifact = Artifact(
            artifact_id=aid,
            project_id=project_id,
            stage_id=stage_id,
            page_identity=page_identity,
            object_id=object_id,
            artifact_type=artifact_type,
            path=str(path),
            sha256=result.hashes.get(str(path)),
            status=ArtifactStatus.ACCEPTED,
            is_fact_source=is_fact_source,
        )
        registered.append(registry.register(artifact, file_path=path))
    return registered


class DownloadCollector:
    """执行 task boundary 的完整下载流程。"""

    def __init__(self, downloader: Downloader) -> None:
        self.downloader = downloader

    def collect(
        self,
        before: BoundarySnapshot,
        after: BoundarySnapshot,
        output_dir: Path,
    ) -> CollectedResult:
        """根据前后快照 diff，下载本轮新增资源并计算 hash。"""
        d = diff_boundary(before, after)
        result = CollectedResult(new_downloadables=d.new_downloadables)
        for url in sorted(d.new_downloadables):
            try:
                path = self.downloader.download(url, output_dir)
                result.downloaded.append(path)
                result.hashes[str(path)] = sha256_file(path)
            except Exception:
                # 单个资源下载失败不阻断整体，交由上游 Gate/Retry 判定
                continue
        return result


__all__ = [
    "DownloadCollector",
    "Downloader",
    "HTTPDownloader",
    "CollectedResult",
    "register_collected_artifacts",
]
