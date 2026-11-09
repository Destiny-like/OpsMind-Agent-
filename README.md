# OpsMind（运维智脑）

> 企业级智能运维助手：RAG 知识库问答 + AIOps 自动故障诊断，基于 LangChain / LangGraph / Milvus 构建，通过 MCP 协议接入日志与监控工具。

![Python](https://img.shields.io/badge/Python-3.11~3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![LangChain](https://img.shields.io/badge/LangChain-Latest-orange)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

## ✨ 核心特性

- 🤖 **智能对话** — LangChain 多轮对话，支持一次性返回与 SSE 流式输出
- 📚 **RAG 知识库问答** — 文档上传、自动分块、向量入库、检索增强，知识库可随时更新
- 🔧 **AIOps 智能诊断** — Plan-Execute-Replan 循环：自动制定诊断计划、调用工具取证、动态重规划、输出根因分析与处置建议
- 🌐 **Web 界面** — 快速问答 / 流式对话 / 智能运维诊断三种模式
- 🔌 **MCP 工具集成** — 日志查询（CLS）与监控数据（Monitor）以 MCP Server 形式提供，工具可热插拔

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
更细的参数可查看 `scripts/oncall_ctl.py` 的子命令：`start` / `stop` / `status` / `logs` / `upload-docs` / `pull-images`。

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
├── scripts/oncall_ctl.py       启停控制：start / stop / status / logs / upload-docs / pull-images
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
在受限网络下可先通过镜像站拉取再重命名，或用 `python scripts/oncall_ctl.py pull-images` 按内置的镜像站列表顺序重试；MinIO 仓库被镜像站屏蔽时，使用覆盖层启动：
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
重新上传即可（同一来源的旧分片会自动覆盖）：`start.bat docs` 或 `python scripts/oncall_ctl.py upload-docs`；彻底清空用 `docker compose -f vector-database.yml down -v`。

## 📚 参考

- [FastAPI](https://fastapi.tiangolo.com/) · [LangChain](https://python.langchain.com/) · [LangGraph Plan-and-Execute](https://langchain-ai.github.io/langgraph/tutorials/plan-and-execute/)
- [Milvus 文档](https://milvus.io/docs) · [Model Context Protocol](https://modelcontextprotocol.io/) · [阿里云百炼](https://help.aliyun.com/zh/model-studio/)

## 📄 License

MIT License © chief
