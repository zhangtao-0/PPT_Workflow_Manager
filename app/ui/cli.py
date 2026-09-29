"""CLI 入口（A7，第三部分 + ADR-003）。

V1 只做 CLI，命令对齐 ADR-003：
    pwm project create --name X
    pwm run project_A [--stage 07B] [--limit N]
    pwm watch project_A
    pwm status project_A
    pwm retry TASK_0012
    pwm resume project_A
    pwm rollback project_A --to 07B   # A9 接入
    pwm inspect TASK_0012

Phase A 严禁连接真实 ChatGPT：run 使用注入的 Executor（默认 EchoExecutor，
A10 用 FakeAdapter 替代做 Stage 00→07B 全链路）。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from app.queue.queue import TaskQueue
from app.registry.db import WorkflowDB
from app.workflow.models import Task, TaskState
from app.workflow.project import ProjectManager
from app.workflow.worker import ExecutionResult, Executor, Worker


class EchoExecutor:
    """Phase A 占位执行器：任何任务直接标为完成。A10 由 FakeAdapter 替代。"""

    def execute(self, task: Task) -> ExecutionResult:
        return ExecutionResult(ok=True)


def default_projects_root() -> Path:
    env = os.environ.get("PWM_PROJECTS_ROOT")
    return Path(env) if env else Path.cwd() / "projects"


def _open_db(projects_root: Path, project_id: str) -> WorkflowDB:
    return WorkflowDB(projects_root / project_id / "runtime" / "workflow.db")


# -- 子命令 --------------------------------------------------------------

def cmd_project_create(args: argparse.Namespace) -> int:
    pm = ProjectManager(args.projects_root)
    p = pm.create(name=args.name, project_id=args.id, project_type=args.type)
    print(f"已创建项目：{p.project_id}（{p.name}）")
    print(f"目录：{p.project_root}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    pm = ProjectManager(args.projects_root)
    if not pm.exists(args.project_id):
        print(f"项目不存在：{args.project_id}", file=sys.stderr)
        return 1
    executor: Executor = args.executor_factory()
    db = _open_db(args.projects_root, args.project_id)
    queue = TaskQueue(db)
    worker = Worker(queue, executor)
    try:
        processed = worker.run(stage_id=args.stage, limit=args.limit)
    finally:
        db.close()
    print(f"处理任务数：{len(processed)}")
    for tid in processed:
        print(f"  {tid}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    pm = ProjectManager(args.projects_root)
    if not pm.exists(args.project_id):
        print(f"项目不存在：{args.project_id}", file=sys.stderr)
        return 1
    db = _open_db(args.projects_root, args.project_id)
    queue = TaskQueue(db)
    try:
        summary = queue.status_summary()
        print("PPT Workflow Manager")
        print(f"\nProject    : {args.project_id}")
        print("\nQueue")
        print("-" * 32)
        print(f"Pending     {summary.get('ready', 0) + summary.get('pending', 0)}")
        print(f"Running     {summary.get('running', 0)}")
        print(f"Completed   {summary.get('completed', 0)}")
        print(f"Failed      {summary.get('retryable_failed', 0) + summary.get('blocked', 0)}")
        running = queue.current_running()
        if running:
            print("\nCurrent Task")
            print("-" * 32)
            print(f"{running}")
    finally:
        db.close()
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    db = _open_db(args.projects_root, args.project_id)
    queue = TaskQueue(db)
    try:
        task = queue.get(args.task_id)
        if task.status not in (TaskState.RETRYABLE_FAILED, TaskState.BLOCKED):
            print(f"任务 {args.task_id} 状态为 {task.status.value}，不可重试", file=sys.stderr)
            return 1
        queue.requeue(args.task_id)
        print(f"任务 {args.task_id} 已重新入队")
    finally:
        db.close()
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    db = _open_db(args.projects_root, args.project_id)
    queue = TaskQueue(db)
    try:
        failed = queue.list(TaskState.RETRYABLE_FAILED)
        for t in failed:
            queue.requeue(t.task_id)
        print(f"已把 {len(failed)} 个失败任务重新入队")
    finally:
        db.close()
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    db = _open_db(args.projects_root, args.project_id)
    queue = TaskQueue(db)
    try:
        task = queue.get(args.task_id)
        print(f"task_id     : {task.task_id}")
        print(f"stage_id    : {task.stage_id}")
        print(f"object_id   : {task.object_id}")
        print(f"status      : {task.status.value}")
        print(f"attempt     : {task.attempt}")
        print(f"priority    : {task.priority}")
    finally:
        db.close()
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    # A10 之后：监听 inbox/ 自动建 Task。Phase A 先给出骨架提示。
    print(f"watch {args.project_id}：持续监听 inbox/（Phase E 完整实现）")
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    # A9 接入
    print(f"rollback {args.project_id} --to {args.to}（A9 接入）")
    return 0


# -- 参数解析 -------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pwm", description="PPT Workflow Manager V1")

    # 公共参数：通过 parent 让每个子命令都能接受 --projects-root
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--projects-root", type=Path, default=None, help="项目根目录")

    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("project", parents=[common], help="项目管理")
    p_create.add_argument("action", choices=["create"])
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--id", default=None)
    p_create.add_argument("--type", default="精品课")

    p_run = sub.add_parser("run", parents=[common], help="执行队列直到结束")
    p_run.add_argument("project_id")
    p_run.add_argument("--stage", default=None)
    p_run.add_argument("--limit", type=int, default=None)

    p_status = sub.add_parser("status", parents=[common], help="查看队列状态")
    p_status.add_argument("project_id")

    p_watch = sub.add_parser("watch", parents=[common], help="监听 inbox 持续处理")
    p_watch.add_argument("project_id")

    p_retry = sub.add_parser("retry", parents=[common], help="重试单个任务")
    p_retry.add_argument("task_id")
    p_retry.add_argument("--project-id", required=True)

    p_resume = sub.add_parser("resume", parents=[common], help="重新入队所有失败任务")
    p_resume.add_argument("project_id")

    p_rollback = sub.add_parser("rollback", parents=[common], help="回退到指定 Stage")
    p_rollback.add_argument("project_id")
    p_rollback.add_argument("--to", required=True)

    p_inspect = sub.add_parser("inspect", parents=[common], help="查看任务详情")
    p_inspect.add_argument("task_id")
    p_inspect.add_argument("--project-id", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.projects_root is None:
        args.projects_root = default_projects_root()

    # executor 工厂：Phase A 默认 EchoExecutor
    args.executor_factory = lambda: EchoExecutor()

    handlers = {
        "project": cmd_project_create,
        "run": cmd_run,
        "status": cmd_status,
        "watch": cmd_watch,
        "retry": cmd_retry,
        "resume": cmd_resume,
        "rollback": cmd_rollback,
        "inspect": cmd_inspect,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
