"""A7 CLI 冒烟测试：project create + run + status 闭环。"""

from __future__ import annotations

import pytest

from app.ui.cli import main


def test_cli_project_create_and_status(tmp_path, capsys):
    rc = main(["project", "create", "--name", "友谊号列车", "--projects-root", str(tmp_path / "projects")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "已创建项目" in out
    # 解析出 project_id
    pid = [l for l in out.splitlines() if "已创建项目" in l][0].split("（")[0].split("：")[1].strip()
    assert pid.startswith("PPT_")


def test_cli_status_empty_project(tmp_path, capsys):
    main(["project", "create", "--name", "X", "--id", "PPT_TEST_STATUS", "--projects-root", str(tmp_path / "projects")])
    capsys.readouterr()
    rc = main(["status", "PPT_TEST_STATUS", "--projects-root", str(tmp_path / "projects")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PPT Workflow Manager" in out
    assert "Completed" in out


def test_cli_run_processes_enqueued(tmp_path, capsys):
    # 建项目后手动入队两个任务，run 应处理掉
    from app.queue.queue import TaskQueue
    from app.registry.db import WorkflowDB
    from app.workflow.models import Task

    root = tmp_path / "projects"
    main(["project", "create", "--name", "X", "--id", "PPT_TEST_RUN", "--projects-root", str(root)])
    capsys.readouterr()

    db = WorkflowDB(root / "PPT_TEST_RUN" / "runtime" / "workflow.db")
    q = TaskQueue(db)
    q.enqueue(Task(task_id="T1", task_type="asset_generation", stage_id="07B", project_id="P"))
    q.enqueue(Task(task_id="T2", task_type="asset_generation", stage_id="07B", project_id="P"))
    db.close()

    rc = main(["run", "PPT_TEST_RUN", "--projects-root", str(root)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "处理任务数：2" in out


def test_cli_project_missing(tmp_path, capsys):
    rc = main(["status", "NOPE", "--projects-root", str(tmp_path / "projects")])
    assert rc == 1
