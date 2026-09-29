"""Project Manager（A4）。

创建/加载 Project：生成 project_id，初始化项目目录，写 project.yaml。

目录结构对齐设计方案 §5（Stage 产物目录）与 ADR-004（runtime/workflow.db、
project_overrides.yaml、pages/、artifacts/）：
    project_root/
    ├─ project.yaml
    ├─ project_overrides.yaml
    ├─ 00_原始资料/ ... 10_审核与交付/   # 各 Stage 产物目录
    ├─ pages/                             # 每页一个 page_manifest 等
    ├─ artifacts/                         # 正式素材事实源
    ├─ runtime/workflow.db                # SQLite 运行时（A3）
    ├─ handoff/work/                      # Work 交接包
    ├─ repair/                            # Repair Mode
    └─ logs/
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime
from pathlib import Path

import yaml

from app.workflow.models import Project, ProjectMode, utcnow

# Stage → 产物目录名（对齐设计方案 §5）
STAGE_DIRS: dict[str, str] = {
    "00": "00_原始资料",
    "01": "01_资料分析",
    "02": "02_教学结构",
    "03": "03_制作指导书",
    "04": "04_分页与页面映射",
    "05": "05_视觉规范",
    "06": "06_缩略图与视觉稿",
    "07": "07_素材",
    "08": "08_PPT分层组装",
    "09": "09_动画与口播",
    "10": "10_审核与交付",
}

# 07_素材 下的子目录
STAGE_07_SUBDIRS: list[str] = [
    "07A_拆解规划",
    "07B_正式素材",
    "批次说明",
    "页面完整包",
]

# 项目级通用目录
COMMON_DIRS: list[str] = [
    "pages",
    "artifacts",
    "runtime",
    "handoff/work",
    "repair",
    "logs",
]


def _slugify(name: str) -> str:
    """中文名无法可靠拼音化，这里只保留 ASCII 字母数字，其余转下划线。

    非 ASCII 名称会得到较短 slug，project_id 仍由时间戳保证唯一。
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return slug or "PROJECT"


def generate_project_id(name: str, now: datetime | None = None) -> str:
    """生成 project_id，形如 PPT_20260929_<SLUG>_<HHMMSS><微秒+随机>。

    尾部含微秒 + 随机后缀，避免同一秒内连续创建项目时碰撞。
    """
    now = now or datetime.now()
    slug = _slugify(name)
    suffix = secrets.token_hex(2)  # 4 位随机，进一步降低碰撞
    return f"PPT_{now.strftime('%Y%m%d')}_{slug}_{now.strftime('%H%M%S%f')}_{suffix}"


class ProjectManager:
    """创建与加载项目的门面。"""

    def __init__(self, projects_root: str | Path) -> None:
        self.projects_root = Path(projects_root)
        self.projects_root.mkdir(parents=True, exist_ok=True)

    # -- 创建 -------------------------------------------------------------
    def create(
        self,
        name: str,
        project_id: str | None = None,
        mode: ProjectMode = ProjectMode.NEW_BUILD,
        project_type: str = "精品课",
        project_root: str | Path | None = None,
    ) -> Project:
        """创建项目：生成 id、建目录、写 project.yaml。"""
        pid = project_id or generate_project_id(name)
        root = Path(project_root) if project_root else self.projects_root / pid
        root.mkdir(parents=True, exist_ok=True)

        project = Project(
            project_id=pid,
            name=name,
            project_type=project_type,
            mode=mode,
            current_stage="00",
            project_root=str(root),
        )

        self._init_dirs(root)
        self._write_project_yaml(root, project)
        self._write_overrides(root)
        return project

    def _init_dirs(self, root: Path) -> None:
        for d in STAGE_DIRS.values():
            (root / d).mkdir(parents=True, exist_ok=True)
        for sub in STAGE_07_SUBDIRS:
            (root / STAGE_DIRS["07"] / sub).mkdir(parents=True, exist_ok=True)
        for d in COMMON_DIRS:
            (root / d).mkdir(parents=True, exist_ok=True)

    def _write_project_yaml(self, root: Path, project: Project) -> None:
        data = project.model_dump(mode="json")
        # created_at/updated_at 用可读 ISO 字符串
        data["created_at"] = project.created_at.isoformat()
        data["updated_at"] = project.updated_at.isoformat()
        (root / "project.yaml").write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def _write_overrides(self, root: Path) -> None:
        """初始化空的项目级 override 文件（ADR-002 分层中的 project_overrides 层）。"""
        override_path = root / "project_overrides.yaml"
        if not override_path.exists():
            override_path.write_text("# 项目级配置覆盖（ADR-002）\n", encoding="utf-8")

    # -- 加载 -------------------------------------------------------------
    def load(self, project_id: str) -> Project:
        """按 project_id 加载已有项目。"""
        root = self.projects_root / project_id
        if not (root / "project.yaml").exists():
            raise FileNotFoundError(f"项目不存在：{project_id}")
        data = yaml.safe_load((root / "project.yaml").read_text(encoding="utf-8")) or {}
        data["project_root"] = str(root)
        return Project.model_validate(data)

    def exists(self, project_id: str) -> bool:
        return (self.projects_root / project_id / "project.yaml").exists()

    def runtime_db_path(self, project_id: str) -> Path:
        return self.projects_root / project_id / "runtime" / "workflow.db"


__all__ = [
    "ProjectManager",
    "generate_project_id",
    "STAGE_DIRS",
    "STAGE_07_SUBDIRS",
    "COMMON_DIRS",
]
