# ADR-001：Workflow 运行模型

**状态：** 已接受（Accepted）
**日期：** 2026-09-29
**决策者：** 项目决策人（先生）

## 结论

> **V1 采用 Single Process Resident Worker + CLI Control Plane；不建设独立 HTTP Service。**

架构上是「常驻 Worker」，部署上仍然只是一个普通 Python 单进程程序。

## 上下文

系统需要一个能「持续运行」的进程：把图片放到一个地方，程序自动一张一张喂给 ChatGPT，收下载、过 Gate、再下一张。这天然要求进程常驻，而不是「执行一条 CLI → 跑完 → Python 退出」的一次性脚本。

但 V1 只有本机、单用户、单浏览器，ChatGPT 并发本来就该保持 1，不需要 HTTP、远程控制、认证、端口。

## 决策

采用如下模型：

```text
CLI
 │
 ▼
Workflow Application
 │
 ▼
Single Process Worker
 │
 ├─ Workflow Engine
 ├─ Queue
 ├─ Scheduler
 ├─ Gate
 ├─ Retry
 ├─ Rollback
 ├─ Artifact Registry
 └─ ChatAdapter
```

CLI 提供两类入口：

```bash
pwm run project_A      # 执行当前已有任务直到队列结束
pwm watch project_A    # 持续监听 projects/project_A/inbox/，放入图片即自动建 Task、排队、喂 ChatGPT
```

`watch` 的行为：

```text
发现输入 → 建 Task → 排队 → ChatGPT → 下载 → Gate → 下一张
```

## 明确不做（V1）

```text
FastAPI / 后台服务 / HTTP API / WebSocket / 进程管理 / 前后端分离
```

## 理由

- 核心需求是「持续自动喂图」，需要常驻进程；
- 服务化会引入 API、端口、认证、生命周期、进程通信、部署，均非当前价值点；
- 保持「单进程 + 单并发」能降低页面风控与浏览器稳定性风险（对齐设计基线第 7 条）。

## 后果

- **正面**：部署简单，心智模型清晰，无网络面，安全面最小。
- **负面**：后续若需远程控制或多用户，需重新评估进程模型（届时走独立 ADR）。
