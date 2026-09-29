# ADR-004：文件事实源与 SQLite 运行态

**状态：** 已接受（Accepted）
**日期：** 2026-09-29
**决策者：** 项目决策人（先生）

## 结论

> **YAML/JSON 是领域与项目事实源；SQLite 自 Phase A 引入，仅负责事务型运行状态、Queue、Retry、TaskRun、Locks 和可重建索引，不取代项目 Manifest。**

文件是领域事实，SQLite 是运行时事实。

## 上下文

Phase A 已有 Queue / Retry / Rollback / FakeAdapter / 完整生命周期。若运行状态全用 JSON（queue.json、task_state.json、retry.json、locks.json…），很快会「自己实现一个非常差的数据库」，且易出现：写一半崩溃导致 JSON 损坏、Task 已执行但状态没写入、Retry 与 Task 状态不同步、Rollback 多文件更新只成功部分。SQLite 原生事务正好解决这些问题，且当前是单机单进程，SQLite 非常合适。

## 决策

### 1. YAML/JSON 继续管什么（领域事实源）

```text
governance/stages/*.yaml
governance/schemas/*.json
governance/gates/*.yaml
governance/templates/*

project.yaml
project_overrides.yaml

page_manifest.json
layer_manifest.json
artifact_manifest.json
page_package_manifest.json
```

这些文件的价值：可 Git diff、可人工审核、可交给 AI、可单独复制、可进入 ZIP、可交给 Work、可长期归档。**必须继续存在。**

### 2. SQLite 从 Phase A 开始管什么（运行时事实）

```text
Queue       : Task / TaskRun
Runtime State: pending / running / completed / failed / waiting_retry
Retry       : attempt / next_retry_at / last_error
Lock        : TASK_01 正在处理（避免重启后重复领取）
Execution History: started_at / finished_at / adapter / conversation / download_event / gate_result
Operational Index : 某 Object 当前最新 Artifact 是哪个（快速查询）
```

### 3. SQLite 不能成为唯一 Artifact Registry

数据库可存 `id / path / status / hash`，但项目目录里仍应有 `artifact_manifest.json`。**删掉 SQLite 不应导致项目文件失去语义**，最多导致 Queue / Runtime Index 需要 rebuild。

### 4. 推荐项目结构

```text
projects/project_A/
├─ project.yaml
├─ project_overrides.yaml
├─ pages/
│  └─ MISSION_01/
│     ├─ page_manifest.json
│     ├─ layer_manifest.json
│     └─ ...
├─ artifacts/
└─ runtime/
   └─ workflow.db
```

后续可提供 `pwm db rebuild project_A`，根据 manifest / artifacts / history 重建运行时索引。

## 后果

- **正面**：事务一致性靠 SQLite 保证；事实源可移植、可审计、可 Git 管理；两者职责边界清晰。
- **负面**：需维护「文件 ↔ 数据库」的一致性约定；重建逻辑需覆盖（由 `pwm db rebuild` 兜底）。
