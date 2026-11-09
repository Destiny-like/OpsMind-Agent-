# OpsMind（运维智脑）

> 一句话：把「人找知识、人问人、人排障」收敛成一条 AI Agent 流水线。

![Python](https://img.shields.io/badge/Python-3.11~3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![LangChain](https://img.shields.io/badge/LangChain-Latest-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

## 项目介绍

OpsMind 是一套面向研发与运维团队的**智能运维 Agent 系统**，通过 AI Agent 解决团队值班中的真实痛点：整合**知识库、对话、运维**三大核心能力，实现**问题自动应答**与**故障智能排查**的一体化服务，致力于降低团队值班的人力成本、提升团队整体效率。

系统的设计中心是 Agent，而不是一个"会聊天的检索框"：知识侧用 RAG 把散落的历史文档、复盘记录和值班手册变成可检索、可引用的答案；对话侧用多轮上下文承接日常重复提问，直接给出可执行的处理步骤；运维侧用 Plan-Execute-Replan 的 Agent 循环，把"服务为什么突然变慢"这类模糊问题自动拆成诊断计划，调用日志与监控工具逐步取证、动态修正判断，最后产出根因分析与处置建议。三块能力共用同一套工具与上下文，因此一次会话里可以从"知识问答"自然衔接到"动手排查"。

## 🎯 解决的三个真实痛点

| 团队痛点 | 传统做法 | OpsMind 的做法 |
|---|---|---|
| 值班被重复问题淹没 | 同一类告警每次都要人再解释一遍 | RAG 知识库自动应答，答案可追溯到文档来源 |
| 排障依赖老手经验 | 新人面对告警无从下手，只能等资深同事 | AIOps Agent 自动生成诊断计划并逐条执行取证 |
| 知识、日志、指标彼此割裂 | 文档在 Wiki、日志在 CLS、指标在监控平台 | 三者收敛到一个入口：对话即检索，诊断即调工具 |

## ✨ 三大核心能力

**1. 知识库 · RAG 自动应答**
Markdown 文档上传后自动分块、调用 embedding 入库（Milvus），检索时按语义召回 Top-K 片段注入上下文；同一来源重复上传会覆盖旧分片，知识库可以持续演进而无需重建索引。

**2. 对话 · 多轮上下文问答**
基于 LangChain 的多轮对话，支持一次性返回与 SSE 流式输出；会话按 Id 隔离上下文，Web 端提供快速问答与流式对话两种模式，答案可边生成边展示。

**3. 运维 · AIOps 智能排查**
Plan-Execute-Replan 三段循环：Planner 制定 4~6 步诊断计划 → Executor 逐步调用 MCP 工具（日志检索、监控指标、服务与工单信息）→ Replanner 评估结果并决定继续、调整或收口，最终输出「告警清单 → 逐项分析 → 根因 → 处置建议」的结构化报告，排查过程全程流式可见。

## 💡 带来的改变

- **对值班同学**：常见问题先问系统，把"等人回复"变成"即时拿到步骤"，夜班被打断的次数显著减少；
- **对新同学**：不用先背熟全部历史故障，Agent 会沿着计划把该看的日志和指标一处处翻出来；
- **对团队沉淀**：知识库与诊断过程都可复用、可追溯，排障经验从"某个人脑子里"变成"系统里的资产"；
- **对工具投入**：日志、监控以 MCP Server 形式接入，新增数据源只需挂一个工具，不改 Agent 主流程。

## 🛠️ 技术栈

| 层 | 选型 |
|---|---|
| Web 框架 | FastAPI + Uvicorn + SSE-Starlette |
| 编排 | LangChain + LangGraph（Plan-Execute-Replan） |
| 大模型 | 阿里云百炼 DashScope（qwen-max / text-embedding-v4） |
| 向量库 | Milvus 2.5（Docker Compose：etcd + MinIO + Milvus + Attu） |
| 工具协议 | MCP（fastmcp，streamable-http） |
| 日志 | Loguru（按天轮转，输出到 logs/） |

## 📦 快速开始

### 环境要求

- Python 3.11 ~ 3.13（3.10 及 3.14 不受支持）
- Docker Desktop（提供 Milvus 向量库）
- 阿里云百炼 API Key（[控制台](https://bailian.console.aliyun.com/)）

### 1. 获取代码

```bash
git clone https://github.com/Destiny-like/OpsMind.git
cd OpsMind
```

### 2. 安装依赖（推荐 uv）

```bash
pip install uv
uv sync                 # 依据 uv.lock 创建 .venv 并安装全部依赖
```

### 3. 配置环境变量

```bash
cp .env.example .env    # Windows: copy .env.example .env
```

编辑 `.env`，至少填入 `DASHSCOPE_API_KEY`。其余项（模型、Milvus 地址、分块参数）均有默认值。

### 4. 启动 Milvus 向量库

```bash
docker compose -f vector-database.yml up -d
```

包含四个容器：`milvus-etcd`、`milvus-minio`、`milvus-standalone`、`milvus-attu`（Attu 控制台 <http://localhost:8000>）。

### 5. 启动 MCP 工具服务

```bash
python mcp_servers/cls_server.py        # 日志查询，127.0.0.1:8003/mcp
python mcp_servers/monitor_server.py    # 监控数据，127.0.0.1:8004/mcp
```

### 6. 启动主服务

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
```

### 7. 建立知识库索引

```bash
for f in aiops-docs/*.md; do curl -s -X POST http://localhost:9900/api/upload -F "file=@$f"; done
```

### Windows 一键脚本

```bat
setup.bat     :: 首次安装：uv sync + 准备 Milvus 镜像
start.bat     :: 一键启动：Docker/Milvus → MCP → FastAPI → 健康检查 → 建索引 → 打开浏览器
stop.bat      :: 停止 API 与 MCP（stop.bat milvus 连 Milvus 容器一起停）
```

`start.bat` 幂等：已运行的服务不会重复拉起，已建好的索引不会重复构建；需要重建索引时执行 `start.bat docs`。
更细的参数可查看 `scripts/opsmind_ctl.py` 的子命令：`start` / `stop` / `status` / `logs` / `upload-docs` / `pull-images`。

### 访问服务

| 入口 | 地址 |
|---|---|
| Web 界面 | <http://localhost:9900> |
| API 文档（Swagger） | <http://localhost:9900/docs> |
| 健康检查 | <http://localhost:9900/health> |
| Milvus Attu 控制台 | <http://localhost:8000> |

## 📡 API 接口

| 功能 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 普通对话 | POST | `/api/chat` | 一次性返回完整回答 |
| 流式对话 | POST | `/api/chat_stream` | SSE 流式输出 |
| AIOps 诊断 | POST | `/api/aiops` | 故障诊断，SSE 流式输出诊断过程 |
| 文档上传 | POST | `/api/upload` | 上传 md/txt 并自动建立向量索引 |
| 健康检查 | GET | `/health` | 返回服务与 Milvus 连接状态 |

```bash
# 普通对话
curl -X POST http://localhost:9900/api/chat \
  -H "Content-Type: application/json" \
  -d '{"Id":"session-1","Question":"服务响应慢怎么排查？"}'

# 流式对话
curl -X POST http://localhost:9900/api/chat_stream \
  -H "Content-Type: application/json" \
  -d '{"Id":"session-1","Question":"你好"}' --no-buffer

# AIOps 诊断
curl -X POST http://localhost:9900/api/aiops \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session-1"}' --no-buffer
```

## 📁 目录结构

```
OpsMind/
├── app/
│   ├── main.py                 FastAPI 入口（lifespan 内连接 Milvus）
│   ├── config.py               配置（Pydantic Settings，读取 .env）
│   ├── api/                    chat / aiops / file / health 路由
│   ├── services/               RAG Agent、AIOps、向量库/嵌入/检索/分块
│   ├── agent/                  MCP 客户端 + AIOps 的 planner / executor / replanner
│   ├── models/                 请求、响应、文档、AIOps 数据模型
│   ├── tools/                  Agent 可用工具（知识库检索、时间）
│   ├── core/                   LLM 工厂、Milvus 客户端
│   └── utils/                  Loguru 日志配置
├── static/                     Web 前端（index.html / app.js / styles.css）
├── mcp_servers/                MCP 服务：cls_server.py(8003)、monitor_server.py(8004)
├── aiops-docs/                 运维知识库（Markdown）
├── scripts/opsmind_ctl.py       启停控制：start / stop / status / logs / upload-docs / pull-images
├── start.bat / stop.bat / setup.bat    Windows 一键启动 / 停止 / 首次安装
├── vector-database.yml         Milvus Docker Compose（etcd + MinIO + Milvus + Attu）
├── vector-database.windows.yml 可选覆盖层：以 bitnami/minio 替代 minio/minio
├── Makefile                    项目管理命令（init / start / stop / restart / lint …）
├── pyproject.toml / uv.lock    依赖与锁定
└── logs/ .run/ volumes/ uploads/   运行时产物（已在 .gitignore 中忽略）
```

## ⚙️ 配置说明

全部配置来自 `.env`（模板见 `.env.example`）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | 空 | **必填**，百炼 API Key |
| `DASHSCOPE_API_BASE` | 官方兼容模式地址 | 可改为自定义网关 |
| `DASHSCOPE_MODEL` | `qwen-max` | 对话模型 |
| `DASHSCOPE_EMBEDDING_MODEL` | `text-embedding-v4` | 向量化模型（1024 维） |
| `MILVUS_HOST` / `MILVUS_PORT` | `localhost` / `19530` | Milvus 连接地址 |
| `RAG_TOP_K` | `3` | 检索返回条数 |
| `CHUNK_MAX_SIZE` / `CHUNK_OVERLAP` | `800` / `100` | 文档分块参数 |

## 🎯 AIOps 诊断流程

```
用户触发 /api/aiops
      │
      ▼
 Planner  ──► 拆解为 4~6 个诊断步骤（明确可用工具与参数）
      │
      ▼
 Executor ──► 逐步执行，调用 MCP 工具（日志检索 / 监控指标 / 服务与工单信息）
      │
      ▼
Replanner ──► 评估结果：继续、调整计划，或收口
      │
      ▼
 输出结构化报告：告警清单 → 逐项分析 → 根因 → 处置建议
```

## 🐛 常见问题

**Milvus 起不来 / `/health` 返回 503**
确认 Docker Desktop 已运行；`docker ps` 能看到 `milvus-standalone` 且状态 healthy；必要时 `docker logs milvus-standalone` 查因，或 `docker compose -f vector-database.yml restart`。

**镜像拉取超时（registry-1.docker.io 不可达）**
在受限网络下可先通过镜像站拉取再重命名，或用 `python scripts/opsmind_ctl.py pull-images` 按内置的镜像站列表顺序重试；MinIO 仓库被镜像站屏蔽时，使用覆盖层启动：
```bash
docker compose -f vector-database.yml -f vector-database.windows.yml up -d
```

**对话报鉴权失败 / 回答为空**
`DASHSCOPE_API_KEY` 无效或额度不足；更换后重启主服务。文档建索引会调用 embedding 接口，额度不足时上传失败，但不影响对话。

**端口被占用（9900 / 8003 / 8004 / 19530）**
```bash
netstat -ano | findstr :9900     # Windows
lsof -i :9900                    # macOS / Linux
```

**重建知识库**
重新上传即可（同一来源的旧分片会自动覆盖）：`start.bat docs` 或 `python scripts/opsmind_ctl.py upload-docs`；彻底清空用 `docker compose -f vector-database.yml down -v`。

## 📚 参考

- [FastAPI](https://fastapi.tiangolo.com/) · [LangChain](https://python.langchain.com/) · [LangGraph Plan-and-Execute](https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/)
- [Milvus 文档](https://milvus.io/docs) · [Model Context Protocol](https://modelcontextprotocol.io/) · [阿里云百炼](https://help.aliyun.com/zh/model-studio/)

## 📄 License

MIT License © chief
