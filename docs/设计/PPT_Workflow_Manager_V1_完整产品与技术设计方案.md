# PPT Workflow Manager V1 完整产品与技术设计方案

**文档状态：** V1 设计基线  
**用途：** 产品设计、技术设计、Codex 开发实施、后续 Workflow Governance Skill 维护  
**适用范围：** 教学 PPT / 精品课 / 公开课 / 比赛课件 / 需要“视觉稿 → 素材拆解 → PowerPoint 分层组装 → 动画 → 审核”的 PPT 项目  
**规范来源：** 《PPT 制作全过程治理 Skill —— 阶段提示词 V2》及其 07A/07B、分层组装、修复模式、缺陷回退规则  

---

## 0. 执行摘要

PPT Workflow Manager V1（下文简称 **PWM**）不是“批量给 ChatGPT 发图片”的脚本，也不是直接替代 PowerPoint 的新编辑器。它是一个**规范驱动、状态可恢复、任务可排队、产物可追踪、阶段可回退**的 PPT 全生命周期工作流管理器。

V1 的核心目标是把当前已经成熟的 PPT 制作治理 Skill，从“需要模型主动记住并遵守的一组 Markdown 提示词”，升级为“由程序实际执行的流程状态机”。

系统采用双层设计：

1. **Governance Layer（治理规范层）**：保留并演进现有 Skill/SOP，定义 Stage、Gate、Page Identity、Object ID、Semantic Layering、缺陷代码、回退规则和交付标准。
2. **Execution Layer（执行层）**：把规范转化为项目状态、Task Queue、Artifact Registry、Adapter 调用、Gate 校验、Retry、Rollback 和 Work Handoff。

V1 的主链路为：

```text
Stage 00 项目初始化
  ↓
Stage 01 原始资料识别与解析
  ↓
Stage 02 教学内容结构化
  ↓
Stage 03 PPT 制作方案与项目指导书
  ↓
Stage 04 页面身份与分页规划
  ↓
Stage 05 视觉风格与模板确定
  ↓
Stage 06 全套页面视觉稿/缩略图
  ↓
Stage 07A 单页语义素材拆解规划
  ↓
Stage 07B 独立高清正式素材生产
  ↓
Stage 08 PowerPoint 语义分层组装
  ↓
Stage 09 动画、讲解与交互设计
  ↓
Stage 10 全局审核、回退、修复与最终交付
```

其中：

- Stage 01–07B 主要利用普通 ChatGPT 聊天模式及浏览器自动化，以控制成本；
- Stage 08 以后可以按任务复杂度选择 Work、PowerPoint 本地构建器、VBA/Python 或人工；
- Stage 07B 的正式素材是后续 PPT 组装的**素材事实源**；
- Stage 10 的缺陷代码不是报告标签，而是**回退路由指令**；
- Page Identity 与 Object ID 必须贯穿完整生命周期，禁止仅依赖页码和 PowerPoint 自动对象名。

---

# 1. 产品定位

## 1.1 产品定义

PWM 是一个面向 PPT 工程流程的本地工作流系统，负责：

- 建立项目；
- 管理原始资料；
- 把治理规范转化为可执行阶段；
- 自动组织发送给 ChatGPT/其他模型的输入；
- 对多页、多对象任务进行单线程任务队列执行；
- 自动收取模型回复及下载资源；
- 维护 Page / Object / Artifact 的稳定身份；
- 为 Work 或 PowerPoint 构建器生成结构化 Page Package；
- 执行阶段 Gate；
- 对失败任务 Retry；
- 对底层缺陷 Rollback；
- 对已有 PPT 执行 Repair Mode；
- 最终形成可继续编辑、可动画、可追溯的 PPT 工程交付物。

## 1.2 V1 解决的核心问题

当前纯聊天式制作主要存在以下问题：

1. 模型容易忘记当前 Stage，出现“进入 07B 后又重新生成 07A 总览”等阶段漂移；
2. 多页任务无法稳定连续执行，需要人工逐页上传；
3. 图片生成完成后，下载资源需要人工逐个收取；
4. 对象编号、文件名、PPT Shape.Name、动画代码名称容易失去一致性；
5. 聊天上下文越来越长后，规则执行稳定性下降；
6. 生成成果散落于聊天中，缺乏可查询的 Artifact Registry；
7. 出现错误时经常只在最终 PPT 上补丁式修复，无法回退真正出错的阶段；
8. Work 模式容易重新生成已有资源，造成成本和一致性浪费；
9. 页码插入、删除、移动后，单纯“第 N 页”定位会失效；
10. 没有程序级 Gate，Stage 之间主要靠人记忆。

PWM V1 的设计原则是：**AI 负责内容判断和生成，程序负责流程状态、身份、合同、校验和交付。**

## 1.3 V1 非目标

V1 不追求：

- 重新实现 PowerPoint 编辑器；
- 同时支持所有 AI 平台；
- 高并发多账号任务农场；
- 绕过平台限制或规避风控；
- 完全无人审核的“全自动精品课生产”；
- 用整页效果图代替正式 PPT；
- 在第一版就实现复杂桌面端 UI Automation；
- 在第一版就支持复杂团队协作与云端数据库。

---

# 2. 设计原则

## 2.1 治理规范与执行引擎分离

Skill/SOP 决定“应该怎么做”，Workflow Engine 决定：

- 当前正在做什么；
- 能不能进入下一阶段；
- 输入从哪里取；
- 输出必须生成什么；
- 失败如何重试；
- 缺陷应回退到哪里。

禁止把全部状态继续藏在 Prompt 中。

## 2.2 Page Identity 高于页码

页码只是当前显示位置。真正的稳定身份必须是：

```text
PAGE_IDENTITY = MISSION_01
CURRENT_INDEX = 7
ORIGINAL_INDEX = 6
```

新增页、删页或插页后，只更新映射，不改变页面身份。

## 2.3 Object ID 贯穿完整生命周期

Stage 07A 一旦锁定对象，Object ID 应贯穿：

```text
07A Object ID
    ↓
07B 文件名
    ↓
Artifact Registry
    ↓
PowerPoint Shape.Name
    ↓
动画表
    ↓
VBA / BAS
    ↓
Stage 10 缺陷报告
```

例如：

```text
CHAR_S07_CRAB
CHAR_S07_CRAB.png
Shapes("CHAR_S07_CRAB")
```

## 2.4 Semantic Layering，而不是 Geometric Slicing

是否拆成独立对象的判断标准是：

- 是否具有独立语义；
- 是否需要独立动画；
- 是否需要独立修改；
- 是否需要独立替换；
- 是否需要独立复用。

禁止机械按矩形裁块。

## 2.5 07A 决定“做什么”，07B 决定“最终交付什么”

Stage 07A 锁定：

- 编号；
- Object ID；
- 名称；
- 对象身份；
- 数量；
- 拆分粒度。

Stage 07B 可以进行高清化、透明化、遮挡补全和必要修正，但不得静默换编号。07B 正式素材与最终说明是后续组装的素材事实源。

## 2.6 一次只执行一个图片生成对象

V1 默认单线程：

```text
Object 01 → 完成/验收/下载
Object 02 → 完成/验收/下载
Object 03 → ...
```

批次是 ZIP 与进度管理单位，不是拼图单位。

## 2.7 Gate 是程序条件，不是聊天提醒

每个 Stage 必须具有机器可判定或“机器 + 人工”联合判定的 Gate。未通过 Gate 不允许自动推进。

## 2.8 Retry 与 Rollback 必须分开

- **Retry**：本阶段任务本身失败，重新执行当前任务；
- **Rollback**：发现输入基线错误或底层缺陷，退回上游 Stage 重建。

例如：

```text
ChatGPT 页面加载超时 → Retry 07B 当前 Object
人物仍带原背景 → Retry 07B 当前 Object
对象本来就拆错了 → Rollback 07A
页面身份对应错误 → Rollback 04
```

## 2.9 不在错误结构上持续打补丁

Stage 10 发现 L01/L02/L03/A01 等基础缺陷时，应回到真正出错层重建。禁止用遮罩、复制、临时裁切掩盖结构错误。

## 2.10 中间产物必须可复用

每一阶段都要产出文件和 Manifest。下游尽量读取文件，不依赖长对话记忆。

---

# 3. 系统总体架构

```text
┌──────────────────────────────────────────────┐
│              Governance Layer                │
│ Skill / SOP / Stage Definition / Checklist   │
│ Gate / Defect Routing / Templates            │
└─────────────────────┬────────────────────────┘
                      │ compile / load
                      ▼
┌──────────────────────────────────────────────┐
│               Workflow Engine                │
│ Project State Machine                        │
│ Stage Orchestrator                           │
│ Task Queue                                   │
│ Gate Validator                               │
│ Retry / Rollback Controller                  │
│ Prompt Resolver                              │
└──────────────┬────────────────┬──────────────┘
               │                │
               ▼                ▼
┌──────────────────────┐  ┌────────────────────┐
│ Adapter Layer         │  │ Artifact Layer     │
│ ChatGPT Adapter       │  │ Artifact Registry  │
│ Image Task Adapter    │  │ File Store         │
│ Work Handoff Adapter  │  │ Hash/Dedup         │
│ PPT Builder Adapter   │  │ Package Builder    │
└─────────────┬────────┘  └──────────┬─────────┘
              │                      │
              ▼                      ▼
      ChatGPT / Work / PPT      Project Workspace
```

## 3.1 Governance Layer

职责：

- 维护 Stage 00–10 定义；
- 维护 Prompt 模板；
- 维护 Input/Output Contract；
- 维护 Gate；
- 维护 Defect Code；
- 维护 Rollback 路由；
- 维护命名规则；
- 维护 SOP 的详细人工说明。

建议目录：

```text
governance/
├─ stages/
│  ├─ 00.yaml
│  ├─ 01.yaml
│  ├─ ...
│  ├─ 07A.yaml
│  ├─ 07B.yaml
│  └─ 10.yaml
├─ prompts/
├─ schemas/
├─ gates/
├─ checklists/
├─ templates/
└─ references/
```

现有 Skill V2 不删除，作为治理规范的人类可读版本；V1 新增机器可读的 `stage_definitions/*.yaml`。

## 3.2 Workflow Engine

核心职责：

- 创建/加载 Project；
- 读取当前状态；
- 计算下一个允许执行的 Stage/Task；
- 创建 Task；
- 调用 Adapter；
- 收集输出；
- 注册 Artifact；
- 执行 Gate；
- Retry；
- Rollback；
- 生成 StageRun 日志。

## 3.3 Adapter Layer

统一接口，不在业务代码中到处写平台判断。

推荐抽象：

```python
class ChatAdapter:
    attach_session()
    open_conversation()
    new_conversation()
    upload_files(files)
    send_text(text)
    submit()
    wait_until_complete()
    get_response_text()
    list_new_downloadables(boundary)
    download(items, output_dir)
    recover_session()
```

V1 Adapter 优先级：

1. `ChatGPTAdapter`：借鉴 chatgpt-py 的浏览器会话、上传、发送、等待和下载能力；
2. `ChatGPTImageTaskAdapter`：借鉴 chatgpt-image-cli 的 task boundary、本轮新增图片识别、增量下载和 task_id；
3. `Queue/UI`：借鉴 PixelQ 的 Pending/Running/Completed/Failed、模板与任务历史设计；
4. `WorkHandoffAdapter`：V1 先生成标准 Package，可手工/半自动交给 Work；
5. DeepSeek / 豆包留到 V2 Adapter 扩展。

## 3.4 Artifact Layer

任何可复用输出都必须注册为 Artifact，而不是只记录文件路径。

Artifact Registry 是系统的“成果索引”，用于：

- 找到某 Page 最新视觉稿；
- 找到某 Object 的正式素材；
- 判断某文件是否被修订；
- 构建 Page Package；
- 判断是否需要重新生成；
- 防止 Work 重复生成已有对象。

---

# 4. 主要领域对象与数据模型

## 4.1 Project

```yaml
project_id: PPT_2026_FRIENDSHIP_TRAIN
name: 友谊号列车
project_type: 精品课
mode: new_build        # new_build | repair
current_stage: "06"
status: active          # active | blocked | completed | archived
created_at: ...
updated_at: ...
project_root: ...
governance_version: ppt-workflow-v1
```

## 4.2 StageRun

记录某一 Stage 的一次实际执行。

```yaml
stage_run_id: SR_20260929_0006
stage_id: "06"
status: running
input_snapshot_id: SNAP_...
started_at: ...
ended_at: null
attempt: 1
executor: chatgpt
conversation_ref: ...
output_artifact_ids: []
gate_result_id: null
```

StageRun 不能被后续重跑覆盖，应保留历史。

## 4.3 Page

```yaml
page_identity: MISSION_01
current_index: 7
original_index: 6
page_name: 童话小信使任务
status: active
page_type: mission
source_refs: [...]
```

约束：

- `page_identity` 项目内唯一；
- 页码变化不改变 Page Identity；
- 删除页面采用状态/Revision，不直接抹掉历史。

## 4.4 PageMapping

用于已有 PPT、插页、漏页、错位审计。

```yaml
current_index: 7
original_index: 6
page_identity: MISSION_01
mapping_status: matched  # matched | added | missing | duplicate | shifted
handling: rebuild
notes: ...
```

## 4.5 ObjectSpec

Stage 07A 的核心对象。

```yaml
object_id: CHAR_MISSION_01_CRAB
page_identity: MISSION_01
sequence: 3
name: 小螃蟹角色
object_type: character
include_scope: 完整角色主体及必要光效
exclude_scope: 背景、对话框、标题
transparent: true
animated: true
ppt_native: false
completion_requirement: 补全被卡片遮挡部分
z_order_group: character
locked: true
revision: 1
```

## 4.6 Task

```yaml
task_id: TASK_07B_MISSION_01_003
task_type: asset_generation
stage_id: "07B"
project_id: ...
page_identity: MISSION_01
object_id: CHAR_MISSION_01_CRAB
status: pending
priority: 100
attempt: 0
max_transport_retry: 3
max_quality_retry: 2
input_artifact_ids: [...]
expected_outputs: [...]
executor: chatgpt_image
idempotency_key: ...
```

Task 状态：

```text
PENDING
→ READY
→ RUNNING
→ WAITING_REMOTE
→ COLLECTING
→ VALIDATING
→ COMPLETED
```

异常分支：

```text
RETRYABLE_FAILED
BLOCKED
ROLLBACK_REQUIRED
CANCELLED
```

## 4.7 Artifact

```yaml
artifact_id: ART_000182
project_id: ...
stage_id: "07B"
page_identity: MISSION_01
object_id: CHAR_MISSION_01_CRAB
artifact_type: transparent_png
path: 07_素材/07B_正式素材/MISSION_01/CHAR_MISSION_01_CRAB.png
sha256: ...
source_executor: chatgpt
source_task_id: TASK_...
revision: 1
status: accepted     # generated | accepted | superseded | rejected
is_fact_source: true
created_at: ...
```

## 4.8 ArtifactRelation

用于记录来源和派生关系：

```text
Stage06 Visual
  ├─derived→ Stage07A Index
  └─referenced_by→ ObjectSpec
ObjectSpec
  └─materialized_as→ Stage07B PNG
Stage07B PNG
  └─assembled_into→ PPT Shape
```

## 4.9 Batch

Stage 07B 的批次不是图像拼图，而是任务/ZIP 管理单位。

```yaml
batch_id: BATCH_MISSION_01_01
range: [1, 5]
object_ids: [...]
status: completed
zip_artifact_id: ART_...
```

## 4.10 GateResult

```yaml
gate_result_id: GATE_07A_MISSION_01_R1
stage_id: "07A"
status: pass          # pass | fail | manual_review
validators:
  - id: unique_object_id
    status: pass
  - id: semantic_layering_review
    status: manual_review
blocking_reasons: []
```

## 4.11 Defect

```yaml
defect_id: DEF_0012
code: L02
severity: P0
page_identity: MISSION_01
object_id: CHAR_MISSION_01_CRAB
description: 人物周围残留原页面矩形背景
rollback_stage: "07B"
status: open
```

## 4.12 Revision

所有会改变锁定身份、ObjectSpec、正式素材事实源的调整必须形成 Revision。

```yaml
revision_id: REV_...
entity_type: ObjectSpec
entity_id: CHAR_MISSION_01_CRAB
from_revision: 1
to_revision: 2
reason: 07B 发现 07A 遮挡范围判断错误
changed_fields: [include_scope, completion_requirement]
approved_by: workflow
```

---

# 5. 文件与目录结构

```text
PPT_Workflow_Manager/
├─ app/
│  ├─ workflow/
│  ├─ queue/
│  ├─ adapters/
│  ├─ registry/
│  ├─ gates/
│  ├─ rollback/
│  ├─ packaging/
│  └─ ui/
├─ governance/
│  ├─ stages/
│  ├─ prompts/
│  ├─ schemas/
│  ├─ checklists/
│  ├─ templates/
│  └─ references/
├─ config/
└─ projects/
```

单个项目：

```text
projects/PPT_2026_FRIENDSHIP_TRAIN/
├─ project.yaml
├─ state.json
├─ registry.sqlite            # V1 可选；最小版也可先 JSON
├─ 00_原始资料/
├─ 01_资料分析/
├─ 02_教学结构/
├─ 03_制作指导书/
├─ 04_分页与页面映射/
├─ 05_视觉规范/
├─ 06_缩略图与视觉稿/
├─ 07_素材/
│  ├─ 07A_拆解规划/
│  ├─ 07B_正式素材/
│  ├─ 批次说明/
│  └─ 页面完整包/
├─ 08_PPT分层组装/
├─ 09_动画与口播/
├─ 10_审核与交付/
├─ handoff/
│  └─ work/
├─ repair/
└─ logs/
```

---

# 6. Contract 模型

每个 Stage 统一由以下 6 部分组成：

```text
Input Contract
Task
Output Contract
Gate
Retry
Rollback
```

## 6.1 Input Contract

明确：

- 必需 Artifact；
- 可选 Artifact；
- 允许的文件类型；
- 版本要求；
- 是否需要人工确认；
- 是否必须从上游 accepted/fact_source 产物读取。

## 6.2 Task

Task 只描述“执行动作”，不承担业务事实存储。

Task 必须具有：

- 唯一 task_id；
- 幂等键；
- 输入快照；
- 执行器；
- Prompt；
- 预期输出；
- 超时/失败状态；
- 本轮下载边界。

## 6.3 Output Contract

每个 Stage 必须声明：

- 必须存在的文件；
- 必须存在的结构化 Manifest；
- 哪些是供人阅读；
- 哪些是供程序读取；
- 哪些 Artifact 成为事实源。

## 6.4 Gate

Gate 分三类：

1. **Machine Gate**：程序可直接判断，如文件存在、Object ID 唯一；
2. **AI Gate**：由审查任务判断，如语义拆分是否过度碎片化；
3. **Human Gate**：如 Stage 06 整体视觉方向最终确认。

## 6.5 Retry

V1 默认分两类：

- Transport Retry：浏览器断开、上传失败、DOM 改动、下载失败；默认最多 3 次；
- Quality Retry：输出缺失、图片不合格、格式错误；默认最多 2 次；

均应可配置。

## 6.6 Rollback

Rollback 不是删掉所有下游成果，而是：

1. 标记受影响 Artifact 为 `superseded` 或 `invalidated`；
2. 计算依赖图影响范围；
3. 保留不受影响页面/对象；
4. 创建新的上游 StageRun；
5. 重新执行必要下游任务。

---

# 7. Stage 00–10 可执行定义

# Stage 00｜项目初始化

## 目标

把“用户给了一堆文件”转换成一个可恢复、可审计、可执行的 Project。

## Input Contract

**必需：**

- 项目名称；
- 至少 1 个原始资料文件或原始页面集合。

**可选：**

- 旧 PPT；
- 正式模板；
- 历史缩略图；
- 旧素材包；
- 用户额外规则；
- 项目类型；
- new_build / repair 模式。

## Task

1. 生成 `project_id`；
2. 创建目录；
3. 对源文件做 inventory；
4. 计算 hash；
5. 判断可读性；
6. 标记文件角色候选；
7. 建立 `source_manifest.json`；
8. 建立初始 `state.json`；
9. 如果检测到旧 PPT 或历史成品，可提示/自动选择 Repair Mode；
10. 不修改原始源文件。

## Output Contract

```text
project.yaml
state.json
00_原始资料/source_manifest.json
00_原始资料/README_来源说明.md
```

结构化字段至少包括：来源文件、文件类型、hash、角色、是否可读取、是否原件、导入时间。

## Gate

- project_id 唯一；
- 至少一个有效源；
- 所有必需源路径存在；
- 原始资料未被覆盖；
- 项目目录可写。

## Retry

- 单文件读取失败：仅重试该文件；
- hash/拷贝失败：最多 3 次；
- 不重建已经成功登记的源。

## Rollback

Stage 00 无业务上游。若初始化失败：

- 删除生成的临时元数据；
- 保留用户原始文件；
- 不执行后续 Stage。

---

# Stage 01｜原始资料识别与解析

## Input Contract

- `source_manifest.json`；
- 所有已登记原始资料；
- 用户明确补充规则。

输入必须来自 Stage 00 accepted sources。

## Task

1. 创建 Stage 01 Chat Task；
2. 将 Stage 01 Prompt 与源文件一起发送；
3. 识别资料类型与权威关系；
4. 提取课程信息、目标、重难点、教学流程；
5. 提取教师行为/学生活动；
6. 提取必须保留内容；
7. 对口播进行初步屏显分流；
8. 显式列出冲突/缺失/待确认；
9. 形成“事实基线”，禁止页面设计。

## Output Contract

```text
01_资料分析/
├─ 原始资料分析.md
├─ facts.json
├─ must_keep.json
├─ conflicts.json
├─ source_relations.json
└─ stage01_manifest.json
```

其中 `facts.json` 必须可供 Stage 02 程序化引用。

## Gate

Machine Gate：

- 所有登记源都有 read_status；
- 必需输出存在；
- conflicts 字段存在，即使为空；
- must_keep 至少可映射到来源。

AI/Human Gate：

- 不把推测写成事实；
- 多源冲突没有被静默合并；
- 后续无需重新通读全部源即可理解事实基线。

## Retry

- 回复中断：Retry 同一任务；
- 漏读某文件：仅创建补充读取 Task，再合并 Stage 01 输出；
- 输出格式错误：进行“结构化修复 Task”，不重新分析全部文件。

## Rollback

- 若发现源文件缺失/损坏/版本错误 → Rollback Stage 00；
- 其他情况停留 Stage 01 修复。

---

# Stage 02｜教学内容结构化

## Input Contract

- Stage 01 `facts.json`；
- `must_keep.json`；
- `conflicts.json`；
- 原始资料仅用于复核，不允许跳过 Stage 01 自由解释。

## Task

1. 提炼课程教学主线；
2. 将长段落拆为 Teaching Event；
3. 标记导入/问题/知识/探索/示例/练习/总结等类型；
4. 对每个事件记录教学目的、教师动作、学生活动；
5. 建立屏显/口播映射；
6. 建立知识依赖；
7. 标记视觉需求及动画需求级别；
8. 形成可分页但尚未分页的结构。

## Output Contract

```text
02_教学结构/
├─ 教学内容结构.md
├─ teaching_events.json
├─ display_speech_map.json
├─ knowledge_dependencies.json
├─ visual_requirements.json
└─ stage02_manifest.json
```

`teaching_events.json` 中每个事件必须带来源追踪字段。

## Gate

- 课程主线存在；
- 每个关键事件均有目的；
- 屏显/口述已区分；
- must_keep 全部能映射到事件；
- 不改变 Stage 01 事实。

## Retry

- 某事件结构不完整：局部重算；
- 输出结构错误：格式修复；
- 不默认重跑 Stage 01。

## Rollback

- 发现 Stage 01 事实错误/漏项 → Stage 01；
- 发现仅结构组织不好 → 留在 Stage 02 重做。

---

# Stage 03｜PPT 制作方案与项目指导书

## Input Contract

- Stage 01 事实基线；
- Stage 02 教学结构；
- 用户附加要求；
- 模板/旧 PPT/视觉参考；
- 项目使用场景。

## Task

1. 判断课件场景；
2. 建立页面比例、兼容性、真人/数字人区域规则；
3. 制定内容密度、标题、正文、题目保留规则；
4. 制定图片、图表、公式、角色、气泡、徽章规则；
5. 制定 Stage 06/07/08/09 的项目级 override；
6. 明确命名、版本、交付；
7. 将模糊审美词转换为可检查约束。

## Output Contract

```text
03_制作指导书/
├─ PPT制作指导书.md
├─ project_overrides.yaml
├─ compatibility.yaml
├─ delivery_rules.yaml
└─ stage03_manifest.json
```

`project_overrides.yaml` 是下游 Prompt Resolver 必须自动加载的项目级规则。

示例：

```yaml
video_safe_zone:
  side: right
  width_ratio: 0.33
  policy: no_core_content
animation:
  default_trigger: click
  transition_seconds: 0.2
powerpoint:
  primary: true
wps_compatibility: secondary
```

## Gate

- 用户明确要求全部转为硬约束；
- 已有正式模板优先；
- 规则可检查；
- 未确定项标记 `pending_confirmation`；
- 不输出最终页数。

## Retry

- 规则模糊：只修订相关规则区；
- 缺失用户要求：补充 override；
- 不重跑 Stage 01/02。

## Rollback

- 若制作指导与真实教学结构冲突 → Stage 02；
- 若仅项目策略错误 → 重跑 Stage 03。

---

# Stage 04｜页面身份与 PPT 分页规划

## Input Contract

- `teaching_events.json`；
- `PPT制作指导书.md`；
- `project_overrides.yaml`；
- `must_keep.json`；
- 旧 PPT/原始逐页视觉稿（若存在）。

## Task

1. 创建 Page 序列；
2. 为每页分配稳定 Page Identity；
3. 定义教学作用、核心内容、屏显文字、讲解重点、学生活动、主视觉、素材需求；
4. 建立必保留内容 → Page 映射；
5. 存在旧 PPT 时建立 Current ↔ Original ↔ Page Identity 映射；
6. 检查漏页/重复页/错位/未经记录的新增页。

## Output Contract

```text
04_分页与页面映射/
├─ PPT页面脚本.md
├─ pages.json
├─ page_mapping.json
├─ required_content_mapping.json
└─ stage04_manifest.json
```

`pages.json` 必须具有不可随页码变化的 `page_identity`。

## Gate

- Page Identity 项目内唯一；
- 页序连续；
- 所有 must_keep 都有归属；
- 不存在未解释重复 Page；
- 已有 PPT 的 page mapping 无 unresolved critical 项；
- 任何新增/删除页均有记录。

## Retry

- 单页职责过载：局部分页重构；
- 单个 mapping 不明确：只重审相关页；
- Page Identity 一旦被下游引用，不可通过普通 Retry 随意改名，必须 Revision。

## Rollback

- 教学结构本身不成立 → Stage 02；
- 项目约束导致分页不可实现 → Stage 03；
- 页码/映射错误 → 本 Stage 重建映射。

---

# Stage 05｜视觉风格与模板确定

## Input Contract

- Stage 03 指导书；
- Stage 04 pages/page script；
- 正式模板；
- 用户参考图；
- 已登记 Brand/课堂风格素材。

## Task

1. 定义风格关键词；
2. 定义色彩用途；
3. 定义字体层级；
4. 定义栅格、安全区和保留区；
5. 定义组件系统；
6. 定义图片/图标风格；
7. 定义页面类型模板；
8. 定义固定元素与可变元素；
9. 如有正式 PPT 模板，提取其约束并标记不可变区域。

## Output Contract

```text
05_视觉规范/
├─ 视觉规范.md
├─ visual_tokens.json
├─ layout_zones.json
├─ component_rules.json
├─ page_type_templates.json
└─ stage05_manifest.json
```

## Gate

- 页面尺寸明确；
- safe zone 明确；
- 模板不可变区明确；
- 色彩/字体写明“用途”而非只列名字；
- 用户指定的视频区等硬约束可机器读取；
- 不改变教学内容。

## Retry

- 单个组件规范缺失：局部补充；
- 视觉规则冲突：生成 conflict report 后修订；
- 模板解析失败：保留人工 override，不阻塞其他已知规则。

## Rollback

- 项目策略需要改变 → Stage 03；
- Page 类型设计不合理 → Stage 04；
- 纯视觉问题停留 Stage 05。

---

# Stage 06｜全套缩略图与页面视觉稿

## Input Contract

- `pages.json`；
- 页面脚本；
- `visual_tokens.json`；
- `layout_zones.json`；
- 项目指导书；
- 模板/参考图。

每一个视觉 Task 必须绑定 `page_identity`。

## Task

采用 Page Queue：

```text
PAGE_001 → 生成/收取/登记/验收
PAGE_002 → ...
```

每个 Page Task：

1. 组装本页 Prompt；
2. 附带页面脚本与视觉约束；
3. 生成/获取完整视觉稿；
4. 下载到本地；
5. 生成页面说明；
6. 注册 Artifact；
7. 更新整套 visual manifest。

可以额外生成全套缩略图总览，但它只是浏览性 Artifact，不能取代每页独立视觉稿。

## Output Contract

```text
06_缩略图与视觉稿/
├─ PAGE_xxx/
│  ├─ visual.png
│  └─ visual_notes.md
├─ thumbnail_overview.png       # 可选/推荐
├─ slide_visual_manifest.json
└─ stage06_manifest.json
```

## Gate

Machine Gate：

- 每个 active Page Identity 都有视觉稿；
- 页数与 Stage 04 一致；
- 每张视觉稿绑定 Page Identity；
- 不存在未登记新增页。

AI/Human Gate：

- 风格一致；
- 主体未侵入硬性保留区；
- 页面职责与脚本一致；
- 整体视觉方向经用户确认后才进入 07A。

## Retry

- 单页视觉失败：只重做该 Page Task；
- 下载失败：只重做收取；
- 模板漂移：使用相同 Page Identity 新 revision，不影响其他通过页面。

## Rollback

- 页数/职责需要改变 → Stage 04；
- 全局风格基线错误 → Stage 05；
- 单页构图问题 → Stage 06 单页重做。

---

# Stage 07A｜单页语义素材拆解规划

## Input Contract

每个 Page 必须提供：

- Stage 06 accepted `visual.png`；
- Page Identity；
- 页面脚本；
- 视觉规范；
- 原始完整幻灯片/视觉稿（若存在）。

## Task

每页独立执行：

1. 分析后续 PowerPoint 需要独立控制的对象；
2. 使用 Semantic Layering 判断拆分；
3. 为对象分配永久 ASCII Object ID；
4. 定义 include/exclude scope；
5. 定义透明规则、动画需求、PPT Native 建议、补全要求；
6. 定义基础 Z-Order；
7. 生成拆解索引图（只展示对象，不重新嵌入原始整页截图）；
8. 生成 `layer_manifest.json`；
9. 生成 Stage 07A ZIP；
10. Gate 通过后锁定对象清单。

## Output Contract

```text
07_素材/07A_拆解规划/PAGE_ID/
├─ decomposition_index.png
├─ decomposition.md
├─ layer_manifest.json
├─ object_specs.json
└─ PAGE_ID_07A.zip
```

`object_specs.json` 是 07B 的唯一任务清单来源。

## Gate

Machine Gate：

- Object ID ASCII；
- Page 内 Object ID 唯一；
- sequence 连续；
- 对象数量 > 0；
- 每对象都有 include/exclude；
- 07A ZIP 存在；
- lock snapshot 已生成。

AI/Human Gate：

- 无明显 Geometric Slicing；
- 无“人物 + 标题 + 背景”过粗合并；
- 无无意义机械碎片化；
- 所有需要独立动画/修改的对象已拆出。

## Retry

- 单个 ObjectSpec 描述不清：修订该对象；
- 整页拆分粒度错误：重跑本页 07A；
- Gate 未通过时不能创建 07B Task。

## Rollback

- 完整视觉稿本身错误 → Stage 06；
- 页面身份/职责错误 → Stage 04；
- 07A 自身拆分错误 → 留在 07A 重建。

**锁定规则：** Gate 通过后，编号、Object ID、名称、数量和拆分粒度进入 locked 状态。后续结构改变必须走 Revision。

---

# Stage 07B｜独立高清正式素材生产

## Input Contract

每个 Task 必须绑定：

- locked `ObjectSpec`；
- Page visual；
- 原始完整幻灯片/视觉参考；
- 07A decomposition；
- 项目视觉规范；
- 前序已 accepted Object Artifact（如对遮挡关系有帮助）。

信息优先级：

```text
07A：决定当前“做谁”
原始视觉：决定“原来长什么样”
07B：决定“最终交付什么样”
```

## Task

Stage 07B 的 Orchestrator 强制执行：

```text
读取 locked object list
↓
寻找最小未完成 sequence
↓
创建单 Object Task
↓
发送当前对象任务
↓
等待当前回复完成
↓
只收取本 Task 新生成资源
↓
下载
↓
单图 Gate
↓
登记 Artifact
↓
继续下一个 Object
```

每个编号 = 一次独立 Task = 一个独立正式文件。

禁止：

- 素材总表；
- Contact Sheet；
- 九宫格；
- 多对象拼图；
- 从 07A 索引图裁切；
- 从低清视觉稿直接放大；
- 在图片像素中写编号或文件名。

## Output Contract

单 Object：

```text
07B_正式素材/PAGE_ID/
├─ OBJECT_ID.png
└─ OBJECT_ID.meta.json
```

单批：

```text
批次说明/BATCH_xx/
├─ batch_notes.md
├─ batch_manifest.json
└─ PAGE_ID_07B_01-05.zip
```

整页完成：

```text
页面完整包/PAGE_ID_07B_ASSETS.zip
final_asset_manifest.json
```

## Gate

### Object Gate

- 文件名与 Object ID 一致；
- 只包含当前对象；
- 非背景默认真实 Alpha；
- 背景已移除独立前景并补全；
- 遮挡对象已合理补全；
- 无背景污染/白边/黑边/索引框；
- 清晰度满足 PPT；
- 本 Task 只登记一个主对象 Artifact；
- 与 07A 有变化时存在 Revision/说明。

### Batch Gate

- 所有批次对象独立文件存在；
- `batch_notes.md` 存在；
- ZIP 存在；
- ZIP 中不以拼图代替独立图片；
- batch status 已更新。

### Page Gate

- 所有 locked ObjectSpec 均有 accepted Artifact；
- `final_asset_manifest.json` 完整；
- 页面完整素材 ZIP 已生成。

## Retry

Transport Retry：

- 页面发送/上传/下载失败 → 当前 Task 最多 3 次；

Quality Retry：

- Alpha 错误、背景污染、清晰度不足、对象范围错误 → 当前 Object 默认最多 2 次；

Retry 不改变 Object ID。

## Rollback

- 只是图像质量问题 → 留在 07B；
- 07A 对象范围/拆分结构错误 → Rollback 07A；
- 整页视觉设计错误 → Rollback 06；
- Page Identity 错误 → Rollback 04。

07B accepted Artifact 标记 `is_fact_source=true`，是 Stage 08 的正式素材事实源。

---

# Stage 08｜PowerPoint 语义分层组装

## Input Contract

必须同时使用：

- Stage 04 Page Script；
- Stage 06 accepted visual；
- Stage 07A layer manifest；
- Stage 07B accepted assets；
- Stage 03 Project Guide；
- Stage 05 Visual Spec；
- 模板 PPTX（若存在）。

建议系统先构建标准 Page Package，再交给执行器。

## Task

执行器可选：

```text
work
local_ppt_builder
manual
```

V1 首选复杂页面使用 Work，简单页面允许本地构建器。

每页执行：

1. 建立/复制正式模板；
2. 放置背景；
3. 放置固定模板元素；
4. 按 Z-Order 组装正式素材；
5. 普通文字优先 PowerPoint Native；
6. 特殊艺术字才使用 PNG；
7. 卡片底板与正文尽量分离；
8. 所有可动画对象使用永久 Object ID 作为 Shape.Name；
9. 生成 Assembly Manifest；
10. 输出与视觉稿差异记录。

## Output Contract

```text
08_PPT分层组装/
├─ project_static.pptx
├─ assembly_manifest.json
├─ shape_map.json
├─ build_diff.md
├─ pages/
│  └─ PAGE_ID_assembly.json
└─ stage08_manifest.json
```

`shape_map.json` 至少记录：

```yaml
object_id: CHAR_MISSION_01_CRAB
page_identity: MISSION_01
shape_name: CHAR_MISSION_01_CRAB
shape_type: picture
source_artifact_id: ART_...
z_order: 5
```

## Gate

Machine Gate：

- PPTX 可打开；
- Page 数量与 active Page Identity 数量一致；
- 所有 required Object 都在 shape_map；
- Shape.Name 唯一且与 Object ID 一致；
- 没有以单张整页图片作为唯一页面结构；
- 文字可编辑策略符合项目规则。

AI/Visual Gate：

- 构图与 Stage 06 一致；
- 无矩形裁切边界；
- 无背景污染；
- 无原图残字与新文字重复；
- 多教学任务没有被烘焙成不可控制的大图。

## Retry

- 单页组装失败 → 单页重建；
- Shape.Name 不一致 → 自动修复/重建 shape map；
- PPTX 保存失败 → 当前构建 Task Retry；
- 不默认重做素材。

## Rollback

- L02/T01 等素材问题 → 07B；
- L01/L03/L04/A01 等拆分结构问题 → 07A；
- Visual 本身错误 → 06；
- Page mapping 错误 → 04。

Stage 08 Static Gate 未通过，不允许大规模进入 Stage 09。

---

# Stage 09｜动画、讲解与交互设计

## Input Contract

- Stage 08 accepted PPTX；
- `shape_map.json`；
- Page Script；
- 教师口播/逐字稿；
- Project Animation Rules；
- 可选音频/视频/数字人素材。

## Task

1. 逐页建立“讲解事件 → 点击 → Shape 变化”；
2. 定义初始可见对象；
3. 定义 Click Step；
4. 使用三类触发：Click / With Previous / After Previous；
5. 证明、推导、答案按认知顺序；
6. 检查音频/视频阻塞；
7. 可生成 BAS/VBA；
8. BAS/VBA 直接引用 Shape.Name，不重新发明对象名；
9. 每页建议独立 Setup 函数；
10. 生成 animation manifest。

## Output Contract

```text
09_动画与口播/
├─ animation_plan.md
├─ animation_manifest.json
├─ narration_map.json
├─ project_animated.pptx          # 若自动设置动画
├─ ApplyAllAnimations.bas         # 可选
└─ stage09_manifest.json
```

## Gate

- animation_manifest 所有对象引用均能在 shape_map 找到；
- 问题/答案顺序正确；
- 默认教师可手动控制；
- 无整页误一次性出现；
- 无明显音频阻塞；
- VBA/BAS 引用名称与 Shape.Name 完全一致；
- 运行动画不会暴露背景污染/矩形裁块。

## Retry

- 单页动画顺序错误 → 只重做该页；
- VBA 编译/对象引用错误 → 修复代码/名称；
- 不因动画参数问题重做全 PPT。

## Rollback

- Shape 不独立/命名问题 → Stage 08；
- 对象本身不具备独立动画条件 → Stage 07A/08；
- 素材图像错误 → Stage 07B。

---

# Stage 10｜全局审核、回退、修复与最终交付

## Input Contract

Stage 00–09 全部 accepted artifacts、项目规则和最终/准最终 PPT。

## Task

审核维度：

1. 教学事实；
2. Page 完整性；
3. 页面映射；
4. 视觉一致性；
5. 素材质量；
6. 分层结构；
7. 动画逻辑；
8. 技术兼容；
9. 文件大小和交付完整性；
10. 教学演练。

每个问题必须生成 Defect：

- code；
- severity；
- Page Identity；
- Object ID（若适用）；
- 证据；
- rollback_stage；
- impact scope。

## Output Contract

```text
10_审核与交付/
├─ 最终审核报告.md
├─ defects.json
├─ delivery_manifest.json
├─ README_交付说明.md
└─ Final/
   ├─ 课程名称_最终版.pptx
   ├─ 动画说明.md
   ├─ 页面脚本.md
   ├─ Assets_正式素材.zip
   └─ 其他约定文件
```

## Gate

- P0 缺陷为 0；
- 所有 P1 已处理或被明确接受；
- 最终 PPT 可打开；
- delivery_manifest 与实际文件一致；
- 项目中不存在仍为 `ROLLBACK_REQUIRED` 的 Stage/Task；
- 所有 final Artifact 均有 hash。

## Retry

- 审核任务中断 → 审核 Retry；
- 单项复验失败 → 只复验相关范围；
- Stage 10 本身不通过普通 Retry 修复底层缺陷。

## Rollback

缺陷路由：

| Code | 缺陷 | 默认 Rollback |
|---|---|---|
| P01 | Page Mapping Error | 04 |
| P02 | Missing Page | 04 → 06 |
| P03 | Unexpected Added Page | 04 / 06 |
| L01 | Geometric Slice | 07A |
| L02 | Background Contamination | 07B |
| L03 | Layer Merge | 07A / 08 |
| L04 | Over Fragmentation | 07A |
| T01 | Duplicate Text | 07B / 08 |
| A01 | Animation Dependency Error | 07A / 08 |
| A02 | Wrong Animation Order | 09 |
| N01 | Object Naming Error | 08 / 09 |

Rollback 后：

```text
标记受影响 Artifact invalidated/superseded
↓
保留无关正确成果
↓
重建指定 Stage
↓
重新执行受影响下游
↓
Stage 10 复验
```

---

# 8. Repair Mode｜已有 PPT 审计与选择性重建

Repair Mode 与 New Build 共用数据模型，但入口不同。

```text
原始资料 / 原始视觉稿 / 当前 PPT
↓
Stage 00 建档
↓
Repair Mapping Audit
↓
Page Identity 映射
↓
Defect 分类
↓
保留 / 局部修补 / 选择性重建 / 整页重建
↓
路由到 04 / 06 / 07A / 07B / 08 / 09
↓
Stage 10 复验
```

## 8.1 Repair 决策类型

每页只能明确归入：

- KEEP；
- PATCH；
- SELECTIVE_REBUILD；
- FULL_PAGE_REBUILD；
- RESTORE_MISSING_PAGE；
- DELETE_CANDIDATE。

## 8.2 选择性重建原则

必须明确：

- 保留项；
- 废弃项；
- 重建项；
- 回退 Stage；
- 依赖受影响范围。

禁止“发现底层错误但仍然在旧错误结构上叠补丁”。

---

# 9. Task Queue 与状态管理

## 9.1 V1 默认单并发

默认：

```yaml
queue:
  concurrency: 1
```

理由：

- 避免 ChatGPT 会话串任务；
- 减少资源边界识别错误；
- 降低页面风控与浏览器稳定性风险；
- 保证“上一任务完成后才开始下一任务”。

## 9.2 队列优先级

建议：

```text
P0 修复任务 > Gate Block 修复 > 当前 Stage 任务 > 后续预生成任务
```

## 9.3 幂等

每个 Task 生成：

```text
idempotency_key = hash(
  stage_id +
  page_identity +
  object_id +
  input_snapshot_hash +
  prompt_version
)
```

同一幂等键已 accepted 时，默认不重复发送。

## 9.4 断点恢复

程序重启时：

1. 加载 state；
2. 检查 RUNNING/WAITING_REMOTE 任务；
3. 若可根据 conversation boundary 恢复，则继续收取；
4. 否则标记 `RECOVERY_REQUIRED`；
5. 不把已 accepted Task 重新发一遍。

---

# 10. ChatGPT 浏览器自动化设计

## 10.1 V1 采用网页端，不优先桌面端 UI Automation

推荐：

- Chrome/Edge；
- 用户自行登录；
- CDP 或持久浏览器 Profile；
- Playwright 驱动。

程序不保存 ChatGPT 密码。

## 10.2 选择器隔离

网页 DOM 易变化。所有 selector 必须集中到 Adapter：

```text
adapters/chatgpt/selectors.py
```

业务代码禁止直接引用网页 selector。

## 10.3 Conversation Strategy

支持：

```yaml
conversation_mode: continue | isolated | batch
batch_size: 10
```

推荐：

- Stage 01–05：按项目 continue 或阶段 isolated；
- Stage 06：可按一组页面 batch；
- Stage 07A：按 Page isolated；
- Stage 07B：按 Page continue，但每 Object 单独 Task；
- 高噪声或上下文过长时自动切新对话，并重新注入必要规范。

## 10.4 Task Boundary

图片/文件下载必须知道“本轮新增了什么”。

每次任务发送前记录：

- 当前 assistant turn 数；
- 当前可下载资源标识；
- 当前图片资源集合；
- conversation id；
- timestamp。

完成后只收取 boundary 之后的新资源。

## 10.5 Download Collector

流程：

```text
snapshot before task
↓
send task
↓
wait complete
↓
snapshot after task
↓
diff downloadables
↓
download
↓
hash + dedup
↓
register Artifact
```

下载完成不等于 Task 完成，仍需 Output Contract / Gate。

---

# 11. Artifact Registry 事实源优先级

## 11.1 Stage 07B 页面素材事实源

后续组装默认使用：

```text
accepted 07B image
↓
07B object meta
↓
final_asset_manifest
↓
07A ObjectSpec
↓
07A decomposition index
↓
Stage 06 visual reference
```

上层与下层冲突时，使用更高层 accepted Artifact；结构性修改必须留 Revision。

## 11.2 Supersede，而不是覆盖

重做文件不直接抹掉旧文件：

```text
CHAR_S07_CRAB_r1.png   status=superseded
CHAR_S07_CRAB_r2.png   status=accepted
```

对用户交付时可以只暴露当前 accepted 版本。

---

# 12. Page Package 与 Work Handoff

Stage 07B 完成后，系统应自动构建标准 Page Package。

```text
PAGE_MISSION_01/
├─ page_manifest.json
├─ page_script.md
├─ visual_reference.png
├─ layer_manifest.json
├─ assets/
│  ├─ BG_MISSION_01.png
│  ├─ CHAR_MISSION_01_CRAB.png
│  ├─ TRAIN_MISSION_01.png
│  ├─ CARD_MISSION_01.png
│  └─ ...
├─ assembly_instruction.md
└─ PAGE_MISSION_01.zip
```

## 12.1 page_manifest.json

至少包括：

- Project ID；
- Page Identity；
- 当前页码；
- 页面职责；
- 视觉参考 Artifact；
- ObjectSpec 列表；
- accepted Asset 列表；
- Z-Order；
- Native Text 建议；
- 保留区；
- 动画需求初标。

## 12.2 Work Handoff 原则

给 Work 的任务应该是：

> “使用已有事实源和素材进行分层组装。”

而不是：

> “根据这张图重新生成一套素材再做 PPT。”

Work 必须优先引用 package 中已有资产。

---

# 13. Prompt Resolver

Prompt 不应永久硬编码在 Adapter 中。

每个任务的最终 Prompt 由以下层合并：

```text
Stage Base Prompt
+ Governance Rules
+ Project Overrides
+ Page Contract
+ Object Contract（若有）
+ Current Task Instruction
+ Retry/Repair Context（若有）
```

优先级：

```text
用户当前明确要求
> Project Overrides
> Locked Object/Page Contract
> Stage Rules
> 通用默认规则
```

Prompt Resolver 必须记录最终 prompt hash，便于重现任务。

---

# 14. Machine-readable Stage Definition 示例

建议把 Stage 07B 编译为类似：

```yaml
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
    - visual_spec
outputs:
  required:
    - object_png
    - object_meta
validators:
  - filename_matches_object_id
  - single_object_only
  - alpha_rule
  - no_index_label_in_pixels
  - quality_minimum
retry:
  transport: 3
  quality: 2
rollback:
  object_structure_error: "07A"
  page_visual_error: "06"
  page_identity_error: "04"
on_page_complete:
  - build_final_asset_manifest
  - create_page_asset_zip
```

Codex 开发时应优先让 Workflow Engine 读取配置，而不是为每个 Stage 写独立硬编码流程。

---

# 15. Gate Validator 设计

## 15.1 通用 Validator

- `file_exists`
- `artifact_registered`
- `hash_valid`
- `json_schema_valid`
- `unique_id`
- `all_dependencies_accepted`
- `expected_count_match`
- `zip_contains_expected_files`

## 15.2 PPT 专用 Validator

- `page_identity_unique`
- `must_keep_mapped`
- `object_id_ascii`
- `object_id_unique`
- `shape_name_matches_object_id`
- `no_full_slide_flatten_only`
- `all_locked_objects_materialized`
- `animation_refs_resolvable`
- `no_unresolved_p0_defect`

## 15.3 AI/视觉 Validator

V1 可先由独立审查 Prompt 执行，输出结构化结果：

```json
{
  "status": "pass",
  "issues": [],
  "confidence": "high"
}
```

AI Gate 只能作为指定 Gate 的一部分，不能替代全部机器校验。

---

# 16. Retry、Failure 与 Recovery 策略

## 16.1 错误分类

```text
TRANSPORT_ERROR
SESSION_ERROR
SELECTOR_ERROR
UPLOAD_ERROR
REMOTE_TIMEOUT
DOWNLOAD_ERROR
OUTPUT_MISSING
OUTPUT_FORMAT_ERROR
QUALITY_ERROR
CONTRACT_ERROR
GATE_FAILED
ROLLBACK_REQUIRED
```

## 16.2 可自动 Retry

适合自动 Retry：

- 网络超时；
- 页面没有加载；
- 上传失败；
- 下载失败；
- 模型回复意外截断；
- 结构化 JSON 缺少字段；
- 当前素材透明背景失败。

## 16.3 不应无限 Retry

以下应升级为 Block/Rollback：

- 同一 Quality Error 连续超过阈值；
- 模型反复违反阶段边界；
- 07A 锁定结构本身错误；
- 页面映射错误；
- 模板基线错误；
- Work 组装发现多个对象不存在。

---

# 17. UI / 操作界面 V1

V1 UI 不需要复杂。建议左中右三栏：

## 17.1 左栏：Project / Stage

```text
友谊号列车

00 ✓
01 ✓
02 ✓
03 ✓
04 ✓
05 ✓
06 18/26
07A 4/26
07B 16/213
08 0/26
09 -
10 -
```

## 17.2 中栏：Task Queue

```text
RUNNING
TASK_07B_MISSION_01_003
CHAR_MISSION_01_CRAB

PENDING
TASK_07B_MISSION_01_004
CARD_MISSION_01_MAIN
...
```

## 17.3 右栏：当前 Contract / Artifact

显示：

- Page Identity；
- Object ID；
- 输入文件；
- Prompt 版本；
- 下载结果；
- Gate 状态；
- Retry 次数；
- Rollback 建议。

## 17.4 必须提供的操作

- Start / Pause Queue；
- Retry Task；
- Accept Artifact；
- Reject Artifact；
- Open Output Folder；
- Re-run Gate；
- Rollback to Stage；
- Build Page Package；
- Export Work Package。

---

# 18. 安全与账号设计

1. 用户自己在浏览器登录 AI 平台；
2. 不在项目配置中存账号密码；
3. CDP 调试端口仅绑定本机；
4. 浏览器 Profile 与项目数据分离；
5. 下载资源先进入 Task 临时目录，Gate 通过后再进入正式 Artifact 目录；
6. 所有外部下载计算 hash；
7. 不自动执行下载到本地的未知脚本/宏；
8. VBA/BAS 生成后仅作为文本/工程文件处理，是否执行由明确阶段负责。

---

# 19. 日志与可观测性

每个 Task 至少记录：

- task_id；
- stage；
- page_identity；
- object_id；
- input snapshot；
- prompt hash；
- conversation ref；
- started/ended；
- response status；
- downloaded resources；
- Gate；
- Retry；
- Error；
- Artifact IDs。

建议日志分：

```text
workflow.log
adapter.log
artifact.log
gate.log
rollback.log
```

禁止把账号凭据写入日志。

---

# 20. V1 数据存储建议

V1 可以分两步：

## V1.0

- YAML/JSON 作为事实文件；
- 文件系统存 Artifact；
- SQLite 可暂缓。

优点：实现快、Codex 容易调试、人工可读。

## V1.1

引入 SQLite 保存：

- Task；
- Artifact；
- StageRun；
- Defect；
- Revision；
- Page/Object 索引。

文件本体仍在项目目录，不把大二进制塞数据库。

---

# 21. V1 开发范围

## 21.1 必须完成（MVP）

1. Project 初始化；
2. Project State；
3. Stage Definition Loader；
4. Task Queue；
5. ChatGPT 浏览器 Adapter；
6. 文件上传；
7. 文本发送；
8. 回复完成检测；
9. 新资源识别；
10. 自动下载；
11. Artifact Registry；
12. Stage 06 Page Queue；
13. Stage 07A Page Task；
14. Stage 07B Object Queue；
15. Batch ZIP；
16. Page Package；
17. Gate；
18. Retry；
19. Rollback 基础路由；
20. Repair Mode 基础映射；
21. Work Handoff Package；
22. 简单 UI 或 CLI 状态页。

## 21.2 V1 可延后

- DeepSeek Adapter；
- 豆包 Adapter；
- 桌面客户端 UI Automation；
- 多账号并发；
- 云端同步；
- 团队权限；
- 自动 PowerPoint 高复杂动画编辑；
- 完全自动的视觉 QA CV 模型。

---

# 22. 推荐实施顺序（交给 Codex）

## Phase A｜只搭骨架，不碰 ChatGPT DOM

1. 定义数据模型；
2. 建 Project Manager；
3. 建 Artifact Registry；
4. 建 Stage Definition Loader；
5. 建 Task Queue；
6. 建 Gate/Retry/Rollback 接口；
7. 用 FakeAdapter 做端到端测试。

**验收：** 不访问网页，也能模拟从 Stage 00 跑到 07B，并生成正确状态和目录。

## Phase B｜接 ChatGPT 基础能力

1. 接管已登录浏览器；
2. 新建/打开聊天；
3. 上传文件；
4. 发送文本；
5. 检测回复完成；
6. 保存回复文本。

**验收：** 一个普通图片/文档任务能从 Task → ChatGPT → 本地 Artifact 完整闭环。

## Phase C｜图片 Task Boundary 与下载

借鉴 chatgpt-image-cli：

1. pre-task snapshot；
2. post-task snapshot；
3. 新图片/附件 diff；
4. download；
5. hash/dedup；
6. Artifact 注册。

**验收：** 连续发送 5 个图片任务，不串任务、不重复下载。

## Phase D｜Stage 07B 先落地

优先实现最能立即产生价值的部分：

```text
folder / locked ObjectSpec
→ 自动逐对象投喂
→ 下载
→ Gate
→ 批次说明
→ ZIP
→ 状态续跑
```

**验收：** 程序重启后能从最小未完成 Object ID 继续。

## Phase E｜扩展 Stage 01–07A

逐步接入：

- 文档分析；
- 教学结构；
- 指导书；
- Page Identity；
- 视觉规范；
- Stage 06 Page Queue；
- 07A ObjectSpec 生成。

## Phase F｜Work Handoff / Stage 08

先实现 Package Builder，不急于自动控制 Work。

**验收：** 一个 Page Package 包含 Stage 08 所需全部事实源，不需要 Work 再生成素材。

## Phase G｜Repair / Stage 10

1. Defect 模型；
2. Rollback 路由；
3. Dependency invalidation；
4. Selective Rebuild；
5. 最终交付 Manifest。

---

# 23. 关键验收测试

## 23.1 状态漂移测试

条件：07A 已完成。用户/模型试图再次生成新的拆解总表。  
预期：Workflow 不创建 07B 之外的新索引 Task，并记录阶段违规。

## 23.2 07B 单对象测试

条件：Page 有 10 个 Object。  
预期：生成 10 个独立 Task、10 个独立文件，不出现一张 10 对象拼图作为完成依据。

## 23.3 断点恢复测试

执行至 Object 05 后强制关闭程序。  
重启后应从 06 继续，不重复提交 01–05。

## 23.4 下载边界测试

同一对话已有 30 张历史图片，新 Task 产生 2 张。  
预期：只下载当前 Task 新资源。

## 23.5 Page Identity 测试

在第 3 页后插入新页。  
预期：后续 current_index 更新，但原 Page Identity 不变；Artifact 仍正确关联。

## 23.6 Rollback 测试

Stage 10 检测 `L02`。  
预期：只把相关 07B Asset 及依赖的 08/09 Page 结果标记失效，不重做无关页面。

## 23.7 Shape Name 测试

07A Object ID 为 `CHAR_S07_CRAB`。  
Stage 08 Shape.Name 与 Stage 09 BAS 引用必须完全一致。

## 23.8 Work Handoff 测试

Page Package 已含 07B accepted 资产。  
Work Task 的 Instruction 明确禁止无必要重新生成已有对象。

---

# 24. 现有 Skill 向 Workflow Governance 的迁移规则

## 24.1 保留原文件

现有：

- Stage 01–10 Prompt；
- 07A/07B；
- 单页拆解 SOP v6；
- 分层组装 SOP；
- Repair Mode；
- Defect Checklist；
- Templates；

继续作为**人类可读规范与 Prompt 源**。

## 24.2 新增机器可读文件

```text
governance/
├─ stages/*.yaml
├─ schemas/*.json
├─ gates/*.yaml
├─ rollback/defect_routes.yaml
└─ prompts/compiled/
```

## 24.3 Prompt 不再承担的职责

以下内容应从 Prompt 中迁出到程序：

- 当前 Stage；
- 已完成编号；
- 最小未完成编号；
- 当前 Page Identity；
- 当前 Object ID；
- Artifact 路径；
- Retry 次数；
- Gate 状态；
- ZIP 是否已经生成；
- 是否允许进入下一阶段。

Prompt 只接收这些事实，不负责“记住”这些事实。

---

# 25. 最终产品边界

PPT Workflow Manager V1 最终应实现的体验是：

用户把项目资料放入项目目录并选择工作流后，系统能够：

```text
建立项目
↓
按 Stage 读取治理规范
↓
自动构造任务
↓
把适合普通 ChatGPT 的工作逐个执行
↓
自动收取回复和下载资源
↓
把结果登记为 Artifact
↓
通过 Gate 后自动进入下一阶段
↓
对视觉稿逐页进行 07A
↓
对 Object 按编号进行 07B 独立高清生产
↓
自动 ZIP 与形成 Page Package
↓
把已完成素材直接交给 Work / PPT Builder 使用
↓
完成分层组装与动画
↓
Stage 10 审核
↓
发现缺陷则精确回退和选择性重建
↓
最终交付
```

系统真正要实现的不是“替人多点几下网页”，而是：

> **把现有 PPT 制作经验固化成一个可执行、可恢复、可验证、可扩展的工程工作流。**

---

# 26. V1 决策基线

以下内容建议作为开发期间不得随意改变的 V1 基线：

1. Governance 与 Execution 分离；
2. Page Identity 高于页码；
3. Stage 07A 锁定 Object Identity；
4. Object ID 使用 ASCII，并贯穿 PNG / Shape.Name / BAS/VBA；
5. Stage 07B 一个 Object = 一个 Task = 一个独立正式文件；
6. Stage 07B 不存在正式“素材总表”；
7. 07B accepted 素材是正式组装事实源；
8. Task Queue V1 默认并发 1；
9. Artifact 不直接覆盖，使用 Revision/Supersede；
10. Stage 08 禁止整页图片冒充正式 PPT；
11. Stage 09 不重新发明对象名称；
12. Stage 10 Defect Code 必须路由到 Rollback；
13. Rollback 采用 Selective Rebuild，不默认全项目重跑；
14. Work 优先消费 Page Package，不重新生成已有正式资产；
15. V1 先把 ChatGPT 网页端跑稳，再扩展 DeepSeek/豆包。

---

# 27. 建议的下一开发文档

完成本设计方案后，Codex 开发前建议继续产出三份更偏实现的文档：

1. **《PPT Workflow Manager V1 数据模型与 JSON Schema 规范》**  
   固定 Project / Page / Object / Task / Artifact / Defect / Revision / Manifest 的字段与版本迁移。

2. **《PPT Workflow Manager V1 Stage Definition YAML 规范》**  
   把 Stage 00–10 全部编译成机器可读 YAML，并定义 Validator/Retry/Rollback 的注册机制。

3. **《PPT Workflow Manager V1 ChatGPT Adapter 实现与 DOM 隔离规范》**  
   具体定义 CDP、会话管理、上传、回复完成检测、task boundary、下载器、selector versioning 和恢复逻辑。

这三份完成后，Codex 即可在不重新解释产品概念的情况下开始工程实现。

---

# 附录 A｜Stage Contract 总表

| Stage | Scope | 主要执行器 | 核心输入 | 核心输出 | 关键 Gate | 典型 Rollback |
|---|---|---|---|---|---|---|
| 00 | Project | Local | 原始资料 | Project/Source Manifest | 源有效 | 无 |
| 01 | Project | ChatGPT | Sources | Fact Baseline | 全源覆盖/冲突显式 | 00 |
| 02 | Project | ChatGPT | Fact Baseline | Teaching Events | 可追溯/屏显口播分流 | 01 |
| 03 | Project | ChatGPT | 01+02+用户规则 | Project Guide | 规则可检查 | 02 |
| 04 | Page Set | ChatGPT | Teaching Events/Guide | Page Script/Page Identity | Page ID 唯一/必保留映射 | 02/03 |
| 05 | Project | ChatGPT | Guide/Pages/Template | Visual Spec | Safe Zone/模板约束明确 | 03/04 |
| 06 | Page | ChatGPT/Image | Page+Visual Spec | Visual Drafts | 全 Page 覆盖/人工确认 | 04/05 |
| 07A | Page | ChatGPT/Image | Accepted Visual | ObjectSpec/Index | Semantic Layering/ID Lock | 06/04 |
| 07B | Object | ChatGPT Image | Locked ObjectSpec | Independent HD Assets | 单对象/Alpha/ZIP | 07A/06 |
| 08 | Page/Deck | Work/PPT Builder | Page Package | Static PPTX/Shape Map | 分层/Shape.Name/可编辑 | 07A/07B/06 |
| 09 | Page/Deck | PPT/VBA/Work | Static PPT/Shape Map/Script | Animation Plan/Animated PPT | 对象可解析/步进正确 | 08/07A |
| 10 | Deck | Audit | All | Defects/Final Delivery | P0=0 | 按 Defect Route |

---

# 附录 B｜Defect Route 基线

```yaml
P01: "04"
P02: "04"
P03: "04"
L01: "07A"
L02: "07B"
L03: ["07A", "08"]
L04: "07A"
T01: ["07B", "08"]
A01: ["07A", "08"]
A02: "09"
N01: ["08", "09"]
```

---

# 附录 C｜V1 术语表

**Governance Layer**：描述规则、Stage、Gate、SOP 的治理规范层。  
**Workflow Engine**：执行状态、任务、Gate、Retry、Rollback 的程序核心。  
**Stage**：完整流程中的职责阶段。  
**StageRun**：某一 Stage 的一次具体执行实例。  
**Page Identity**：不随页码变化的页面稳定身份。  
**Object ID**：Stage 07A 生成并贯穿后续的对象稳定身份。  
**Semantic Layering**：以语义、动画、修改、替换和复用需求决定图层。  
**Artifact**：工作流中可被登记、复用、版本化的任何产物。  
**Artifact Registry**：记录所有 Artifact 身份、版本、来源和关系的索引。  
**Gate**：Stage 是否允许完成或推进的验收条件。  
**Retry**：当前 Task/Stage 因临时或质量问题重新执行。  
**Rollback**：因上游基线错误回退至真正出错的 Stage。  
**Selective Rebuild**：只重建受缺陷影响的页面、对象和依赖产物。  
**Page Package**：给 Stage 08/Work 使用的标准化单页制作包。  
**Task Boundary**：区分本次 AI 任务新增回复/下载资源与历史资源的边界。  
**Fact Source**：发生冲突时拥有更高事实优先级的 accepted Artifact。  

