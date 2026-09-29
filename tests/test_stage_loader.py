"""A6 Stage Definition Loader 测试。"""

from __future__ import annotations

import pytest

from app.workflow.stage_loader import StageDefinition, StageLoader


@pytest.fixture
def stages_dir(tmp_path):
    d = tmp_path / "governance" / "stages"
    d.mkdir(parents=True)
    (d / "07B.yaml").write_text(
        """
id: "07B"
name: independent_hd_asset_production
prerequisites:
  - stage: "07A"
    gate: passed
executor: chatgpt_image
scope: object
queue:
  ordering: sequence_asc
  concurrency: 1
inputs:
  required:
    - locked_object_spec
    - page_visual
outputs:
  required:
    - object_png
    - object_meta
validators:
  - filename_matches_object_id
  - single_object_only
retry:
  transport: 3
  quality: 2
rollback:
  object_structure_error: "07A"
  page_visual_error: "06"
""",
        encoding="utf-8",
    )
    (d / "08.yaml").write_text(
        """
id: "08"
name: ppt_semantic_assembly
prerequisites:
  - stage: "07B"
    gate: passed
executor: work
scope: page
""",
        encoding="utf-8",
    )
    return d


def test_load_all_stages(stages_dir):
    loader = StageLoader(stages_dir)
    assert len(loader) == 2
    assert loader.has("07B")
    assert loader.has("08")


def test_get_parses_fields(stages_dir):
    loader = StageLoader(stages_dir)
    d = loader.get("07B")
    assert d.id == "07B"
    assert d.name == "independent_hd_asset_production"
    assert d.scope == "object"
    assert d.executor == "chatgpt_image"
    assert d.prerequisite_stage_ids == ["07A"]
    assert d.inputs.required == ["locked_object_spec", "page_visual"]
    assert d.outputs.required == ["object_png", "object_meta"]
    assert d.retry.transport == 3
    assert d.retry.quality == 2
    assert d.rollback["object_structure_error"] == "07A"


def test_get_missing_raises(stages_dir):
    loader = StageLoader(stages_dir)
    with pytest.raises(KeyError):
        loader.get("99")


def test_all_sorted(stages_dir):
    loader = StageLoader(stages_dir)
    ids = [d.id for d in loader.all()]
    assert ids == ["07B", "08"]


def test_defaults_when_minimal(stages_dir):
    loader = StageLoader(stages_dir)
    d = loader.get("08")
    assert d.queue.concurrency == 1
    assert d.validators == []
    assert d.inputs.required == []


def test_empty_dir_returns_empty(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    loader = StageLoader(d)
    assert len(loader) == 0
