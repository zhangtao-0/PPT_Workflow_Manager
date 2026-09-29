"""C1/C2/C4 下载边界测试。

核心（§23.4）：同一对话已有 30 张历史图片，新 Task 产生 2 张，
只下载当前 Task 新资源，不重复下载历史。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.adapters.chatgpt.boundary import BoundarySnapshot, diff_boundary
from app.adapters.chatgpt.downloader import (
    CollectedResult,
    DownloadCollector,
    register_collected_artifacts,
)
from app.registry.registry import ArtifactRegistry


# ---------------------------------------------------------------------------
# C1：boundary diff
# ---------------------------------------------------------------------------

def test_diff_same_conversation_incremental():
    before = BoundarySnapshot.capture(
        "conv_1", assistant_turn_count=10,
        downloadables={f"https://x/img_{i}.png" for i in range(30)},  # 30 张历史
    )
    after = BoundarySnapshot.capture(
        "conv_1", assistant_turn_count=12,
        downloadables={f"https://x/img_{i}.png" for i in range(32)},  # +2 张新
    )
    d = diff_boundary(before, after)
    assert d.new_downloadables == {"https://x/img_30.png", "https://x/img_31.png"}
    assert d.turn_delta == 2


def test_diff_conversation_changed_treats_all_as_new():
    before = BoundarySnapshot.capture("conv_1", 5, {"a", "b"})
    after = BoundarySnapshot.capture("conv_2", 1, {"c"})
    d = diff_boundary(before, after)
    # 换了对话，after 全部视为新增
    assert d.new_downloadables == {"c"}


def test_diff_no_change():
    s = BoundarySnapshot.capture("conv_1", 3, {"a", "b"})
    d = diff_boundary(s, s)
    assert not d.has_new
    assert d.new_downloadables == frozenset()


# ---------------------------------------------------------------------------
# C2：collector
# ---------------------------------------------------------------------------

class _FakeDownloader:
    """把 URL 落地为文件内容（内容 = URL 编码后的字节）。"""

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        self.calls: list[str] = []

    def download(self, url: str, output_dir: Path) -> Path:
        self.calls.append(url)
        output_dir.mkdir(parents=True, exist_ok=True)
        name = url.split("/")[-1]
        p = output_dir / name
        p.write_bytes(url.encode("utf-8"))
        return p


def test_collector_downloads_only_new(tmp_path):
    out = tmp_path / "downloads"
    before = BoundarySnapshot.capture("c", 10, {f"https://x/img_{i}.png" for i in range(30)})
    after = BoundarySnapshot.capture("c", 12, {f"https://x/img_{i}.png" for i in range(32)})

    dl = _FakeDownloader(tmp_path)
    collector = DownloadCollector(downloader=dl)
    result = collector.collect(before, after, out)

    assert result.new_downloadables == {"https://x/img_30.png", "https://x/img_31.png"}
    assert len(result.downloaded) == 2
    # 只下载了 2 个新资源，没碰 30 张历史
    assert set(dl.calls) == {"https://x/img_30.png", "https://x/img_31.png"}
    # 每个都有 hash
    assert len(result.hashes) == 2


def test_collector_no_new_does_nothing(tmp_path):
    out = tmp_path / "downloads"
    s = BoundarySnapshot.capture("c", 5, {"a", "b"})
    dl = _FakeDownloader(tmp_path)
    result = DownloadCollector(dl).collect(s, s, out)
    assert result.downloaded == []
    assert dl.calls == []


def test_collector_skips_failed_download(tmp_path):
    class _Fail:
        def download(self, url, output_dir):
            raise OSError("boom")

    out = tmp_path / "downloads"
    before = BoundarySnapshot.capture("c", 0)
    after = BoundarySnapshot.capture("c", 1, {"https://x/a.png"})
    result = DownloadCollector(_Fail()).collect(before, after, out)
    # 失败不阻断，但 downloaded 为空
    assert result.downloaded == []


# ---------------------------------------------------------------------------
# C3：自动注册
# ---------------------------------------------------------------------------

def test_register_collected_artifacts(tmp_path):
    registry = ArtifactRegistry(tmp_path / "artifacts" / "artifact_manifest.json")
    dl = _FakeDownloader(tmp_path)
    before = BoundarySnapshot.capture("c", 0)
    after = BoundarySnapshot.capture("c", 1, {"https://x/CHAR_S07_CRAB.png"})
    result = DownloadCollector(dl).collect(before, after, tmp_path / "downloads")

    artifacts = register_collected_artifacts(
        result, registry, project_id="P1", stage_id="07B",
        object_id="CHAR_S07_CRAB", is_fact_source=True,
    )
    assert len(artifacts) == 1
    a = artifacts[0]
    assert a.sha256 is not None
    assert a.is_fact_source is True
    # registry 里可查到
    assert registry.by_id(a.artifact_id) is not None


# ---------------------------------------------------------------------------
# C5：dedup（同 hash 不重复登记）
# ---------------------------------------------------------------------------

def test_dedup_same_content(tmp_path):
    registry = ArtifactRegistry(tmp_path / "artifacts" / "artifact_manifest.json")
    dl = _FakeDownloader(tmp_path)
    before = BoundarySnapshot.capture("c", 0)
    after = BoundarySnapshot.capture("c", 1, {"https://x/dup.png"})
    result = DownloadCollector(dl).collect(before, after, tmp_path / "downloads")

    # 登记两次相同内容
    first = register_collected_artifacts(result, registry, project_id="P", stage_id="07B", object_id="O")
    second = register_collected_artifacts(result, registry, project_id="P", stage_id="07B", object_id="O")
    # 第二次去重，不新增记录
    assert registry.count() == 1
    assert first[0].artifact_id == second[0].artifact_id


def test_find_by_hash_cross_object(tmp_path):
    """C5：同 sha256 可跨 object 查到，用于防 Work 重复生成（§12.2）。"""
    registry = ArtifactRegistry(tmp_path / "artifacts" / "artifact_manifest.json")
    dl = _FakeDownloader(tmp_path)
    before = BoundarySnapshot.capture("c", 0)
    after = BoundarySnapshot.capture("c", 1, {"https://x/content.png"})
    result = DownloadCollector(dl).collect(before, after, tmp_path / "downloads")

    register_collected_artifacts(result, registry, project_id="P", stage_id="07B", object_id="OBJ_A")
    h = list(result.hashes.values())[0]
    assert registry.has_hash(h)
    found = registry.find_by_hash(h)
    assert len(found) == 1
    assert found[0].object_id == "OBJ_A"
