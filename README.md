# PPT Workflow Manager V1

规范驱动、状态可恢复、任务可排队、产物可追踪、阶段可回退的 **PPT 全生命周期工作流管理器**。

> 把已经成熟的 PPT 制作治理 Skill，从「需要模型主动记住的一组 Markdown 提示词」，升级为「由程序实际执行的流程状态机」。

## 核心设计

双层架构：**Governance Layer（治理规范层）** 决定「应该怎么做」，**Execution Layer（执行层）** 决定「当前正在做什么、能否推进、失败如何重试/回退」。

```
Stage 00 项目初始化 → 01 资料识别 → 02 教学结构化 → 03 制作指导书
→ 04 页面身份与分页 → 05 视觉规范 → 06 视觉稿 → 07A 素材拆解规划
→ 07B 独立高清素材生产 → 08 PPT分层组装 → 09 动画与讲解 → 10 审核交付
```

## 目录结构

```
app/            执行层代码（workflow / queue / adapters / registry / gates / rollback / packaging / ui）
governance/     治理规范层（stages / prompts / schemas / gates / checklists / templates / references）
config/         全局配置
projects/       项目工作区（每项目一目录）
docs/           设计文档与任务分解
tests/          测试
scripts/        辅助脚本
```

## 技术栈

- Python 3.13（Workflow Engine / Adapter / Registry / Gate）
- Playwright + CDP（ChatGPT 网页端自动化）
- YAML/JSON 领域事实源 + SQLite 运行时状态库（Phase A 起）
- 单进程常驻 Worker + CLI 控制入口（V1 无 Web UI）

## 快速开始

```bash
pwm project create --name "友谊号列车"
pwm run project_A      # 执行队列直到结束
pwm watch project_A    # 监听 inbox/ 持续喂图
pwm status project_A   # 查看队列与当前任务
```

## 文档

- [完整产品与技术设计方案](docs/设计/PPT_Workflow_Manager_V1_完整产品与技术设计方案.md)
- [任务分解与实施计划](docs/tasks/01_任务分解与实施计划.md)
- [架构决策记录（ADR）](docs/设计/ADR/)

## V1 决策基线（不可随意变更）

**领域（设计基线）**

1. Governance 与 Execution 分离
2. Page Identity 高于页码
3. Stage 07A 锁定 Object Identity
4. Object ID 使用 ASCII，贯穿 PNG / Shape.Name / BAS/VBA
5. Stage 07B 一个 Object = 一个 Task = 一个独立正式文件
6. 07B accepted 素材是正式组装事实源
7. Task Queue V1 默认并发 1
8. Artifact 不直接覆盖，使用 Revision/Supersede
9. Stage 08 禁止整页图片冒充正式 PPT
10. Stage 10 Defect Code 必须路由到 Rollback

**工程（研发前 4 项决策，见 ADR）**

11. 单进程常驻 Worker + CLI 控制入口，不建设 HTTP Service（ADR-001）
12. 配置分层覆盖 + Governance 最终约束校验，HARD/PROJECT/RUNTIME 三档（ADR-002）
13. V1 只做 CLI，Local Web UI 延后至 V1.1/V2（ADR-003）
14. YAML/JSON 为领域事实源，SQLite 为运行时状态库，不取代 Manifest（ADR-004）
