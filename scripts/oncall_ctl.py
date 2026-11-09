r"""OpsMind 本地启停控制脚本（Windows）

用法（在项目根目录）：
    .venv\Scripts\python.exe scripts\oncall_ctl.py start    # 一键启动全部依赖与服务
    .venv\Scripts\python.exe scripts\oncall_ctl.py stop     # 停止 API / MCP / Milvus 容器
    .venv\Scripts\python.exe scripts\oncall_ctl.py status    # 查看端口、容器与健康状态
    .venv\Scripts\python.exe scripts\oncall_ctl.py logs      # 查看各服务最近日志
    .venv\Scripts\python.exe scripts\oncall_ctl.py upload-docs [--force]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / ".run"
LOG_DIR = ROOT / "logs"
COMPOSE_FILE = ROOT / "vector-database.yml"
COMPOSE_OVERRIDE = ROOT / "vector-database.windows.yml"
COMPOSE_ARGS = ["-f", str(COMPOSE_FILE)] + (
    ["-f", str(COMPOSE_OVERRIDE)] if COMPOSE_OVERRIDE.exists() else []
)
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
DOCS_DIR = ROOT / "aiops-docs"

API_PORT = 9900
API_HEALTH = f"http://127.0.0.1:{API_PORT}/health"
MILVUS_PORT = 19530
MCP_SERVICES = (
    ("cls", "mcp_servers/cls_server.py", 8003),
    ("monitor", "mcp_servers/monitor_server.py", 8004),
)
DOCKER_DESKTOP_CANDIDATES = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/DockerDesktop/Docker Desktop.exe",
    Path(r"C:\Program Files\Docker\Docker\Docker Desktop.exe"),
)


def say(msg: str = "") -> None:
    print(msg, flush=True)


def step(msg: str) -> None:
    say(f"\n[{time.strftime('%H:%M:%S')}] {msg}")


# ---------------------------------------------------------------- 基础工具
def port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_port(port: int, timeout: float, label: str = "") -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(port):
            return True
        time.sleep(1)
    return False


def http_json(url: str, timeout: float = 5.0) -> tuple[int, dict | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # 4xx/5xx 也带 JSON body
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except Exception:
            return exc.code, None
    except Exception:
        return 0, None


def run(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def port_pids(port: int) -> list[int]:
    """返回监听指定 TCP 端口的进程 PID（Windows netstat 解析）"""
    out = run(["netstat", "-ano", "-p", "TCP"]).stdout
    pids: list[int] = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[3] != "LISTENING":
            continue
        if parts[1].endswith(f":{port}") and parts[4].isdigit():
            pid = int(parts[4])
            if pid not in pids:
                pids.append(pid)
    return pids


def kill_port(port: int, label: str) -> bool:
    pids = port_pids(port)
    if not pids:
        say(f"  {label} (端口 {port}) 未运行")
        return False
    for pid in pids:
        run(["taskkill", "/F", "/T", "/PID", str(pid)])
    say(f"  已停止 {label} (端口 {port}, PID {', '.join(map(str, pids))})")
    return True


def pid_file(name: str) -> Path:
    return RUN_DIR / f"{name}.pid"


def read_pid(name: str) -> int | None:
    path = pid_file(name)
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def write_pid(name: str, pid: int) -> None:
    RUN_DIR.mkdir(exist_ok=True)
    pid_file(name).write_text(str(pid), encoding="utf-8")


def clear_pid(name: str) -> None:
    pid_file(name).unlink(missing_ok=True)


def spawn(name: str, args: list[str], log_name: str) -> int:
    """后台分离进程启动，输出重定向到 logs/<log_name>.log"""
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"{log_name}.log"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    base_flags = 0
    if sys.platform == "win32":
        # DETACHED_PROCESS: 脱离调用方控制台；BREAKAWAY: 脱离调用方所在的作业对象，
        # 这样即使 start.bat 退出，服务也继续在后台运行。
        base_flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)  # type: ignore[attr-defined]

    def _launch(flags: int) -> subprocess.Popen:
        with log_path.open("ab") as logf:
            return subprocess.Popen(
                args,
                cwd=str(ROOT),
                stdin=subprocess.DEVNULL,
                stdout=logf,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=flags,
            )

    try:
        proc = _launch(base_flags | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000))
    except OSError:
        proc = _launch(base_flags)
    write_pid(name, proc.pid)
    return proc.pid


# ---------------------------------------------------------------- 依赖检查
def check_env_key() -> bool:
    """只报告 .env 中 DASHSCOPE_API_KEY 是否已填写，绝不打印密钥内容"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        say("  [警告] 未找到 .env 文件，请复制配置模板后填写 DASHSCOPE_API_KEY")
        return False
    value = ""
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("DASHSCOPE_API_KEY"):
            value = line.split("=", 1)[1].strip().strip('"').strip("'") if "=" in line else ""
    if not value or "your-api-key" in value.lower():
        say("  [警告] .env 中的 DASHSCOPE_API_KEY 为空或仍是占位符，对话与建索引会失败")
        return False
    say(f"  DASHSCOPE_API_KEY 已配置（长度 {len(value)}，内容不显示）")
    return True


# ---------------------------------------------------------------- Docker / Milvus
def docker_running() -> bool:
    return run(["docker", "info"]).returncode == 0


def start_docker_desktop(wait: float = 180.0) -> bool:
    exe = next((p for p in DOCKER_DESKTOP_CANDIDATES if p and p.exists()), None)
    if exe is None:
        say("  [错误] 未找到 Docker Desktop，请先安装：https://www.docker.com/products/docker-desktop/")
        return False
    say(f"  正在启动 Docker Desktop: {exe}")
    subprocess.Popen([str(exe)], close_fds=True,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    deadline = time.time() + wait
    while time.time() < deadline:
        if docker_running():
            say("  Docker 引擎就绪")
            return True
        time.sleep(3)
    say("  [错误] Docker 引擎启动超时，请手动打开 Docker Desktop 后重试")
    return False


def milvus_up() -> bool:
    names = run(["docker", "ps", "--format", "{{.Names}}"]).stdout
    return "milvus-standalone" in names


def ensure_milvus() -> bool:
    if milvus_up():
        say("  Milvus 容器已在运行")
    else:
        say("  正在启动 Milvus 容器（etcd / minio / milvus / attu）...")
        res = run(["docker", "compose", *COMPOSE_ARGS, "up", "-d"])
        if res.returncode != 0:
            say("  [错误] Milvus 启动失败：")
            say((res.stderr or res.stdout).strip()[-1500:])
            say("  提示：若报镜像拉取失败（registry-1.docker.io 超时），")
            say("        请先执行 setup.bat 或按《部署与启动说明.md》用镜像站拉取镜像。")
            return False
    if not wait_port(MILVUS_PORT, 180):
        if not wait_port(MILVUS_PORT, 60):
            say("  [错误] Milvus 19530 端口未就绪，请查看 docker logs milvus-standalone")
            return False
    say("  Milvus 就绪 (19530)")
    return True


# ---------------------------------------------------------------- 服务启停
def start_mcp() -> bool:
    ok = True
    for name, script, port in MCP_SERVICES:
        if port_open(port):
            say(f"  {name} MCP (端口 {port}) 已在运行")
            continue
        pid = spawn(f"mcp_{name}", [str(PYTHON), script], f"mcp_{name}")
        if wait_port(port, 30):
            say(f"  {name} MCP 已启动 (端口 {port}, PID {pid})")
        else:
            say(f"  [错误] {name} MCP 启动失败，见 logs/mcp_{name}.log")
            ok = False
    return ok


def start_api() -> bool:
    if port_open(API_PORT):
        say(f"  API (端口 {API_PORT}) 已在运行")
    else:
        pid = spawn("api", [str(PYTHON), "-m", "uvicorn", "app.main:app",
                            "--host", "0.0.0.0", "--port", str(API_PORT)], "api")
        say(f"  API 启动中 (PID {pid})，日志 logs/api.log")
    deadline = time.time() + 120
    while time.time() < deadline:
        status, body = http_json(API_HEALTH, timeout=3)
        if status == 200:
            say("  健康检查通过，Milvus 连接正常")
            return True
        if status == 503:
            say("  [警告] API 已启动但 Milvus 未连通，RAG/检索功能不可用")
            return True
        time.sleep(2)
    say("  [错误] API 未在 120 秒内就绪，见 logs/api.log")
    return False


def upload_docs(force: bool = False) -> bool:
    marker = RUN_DIR / "docs_indexed"
    if marker.exists() and not force:
        say("  知识库已建立过向量索引，跳过（如需重建：start.bat docs）")
        return True
    files = sorted(DOCS_DIR.glob("*.md"))
    if not files:
        say("  aiops-docs 下没有 md 文档，跳过")
        return True
    say(f"  正在上传并建立索引：{len(files)} 个文档（首次较慢，需调用 embedding 接口）")
    ok = True
    for path in files:
        boundary = uuid.uuid4().hex
        body = b"".join([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode(),
            b"Content-Type: text/markdown\r\n\r\n",
            path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        req = urllib.request.Request(
            f"http://127.0.0.1:{API_PORT}/api/upload", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                say(f"    OK   {path.name} ({resp.status})")
        except Exception as exc:
            say(f"    FAIL {path.name}: {exc}")
            ok = False
    RUN_DIR.mkdir(exist_ok=True)
    if ok:
        marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return ok


# ---------------------------------------------------------------- 子命令
def cmd_start(args: argparse.Namespace) -> int:
    say("=" * 62)
    say("  OpsMind 运维智脑 · 一键启动")
    say("=" * 62)

    step("1/5 检查运行环境")
    if not PYTHON.exists():
        say(f"  [错误] 未找到虚拟环境：{PYTHON}")
        say("         请先运行 setup.bat 完成首次安装")
        return 1
    say(f"  Python 环境: {PYTHON}")
    key_ok = check_env_key()

    step("2/5 检查 Docker 与 Milvus 向量库")
    if not docker_running():
        say("  Docker 引擎未运行")
        if not start_docker_desktop():
            return 1
    else:
        say("  Docker 引擎运行中")
    if not ensure_milvus():
        return 1

    step("3/5 启动 MCP 服务（CLS 8003 / Monitor 8004）")
    if not start_mcp():
        return 1

    step("4/5 启动 FastAPI 主服务（9900）")
    if not start_api():
        return 1

    step("5/5 知识库文档索引")
    if not key_ok:
        say("  跳过：需要有效的 DASHSCOPE_API_KEY")
    else:
        upload_docs(force=args.force_docs)

    say("\n" + "=" * 62)
    say("  启动完成")
    say(f"  Web 界面 : http://localhost:{API_PORT}")
    say(f"  API 文档 : http://localhost:{API_PORT}/docs")
    say("  Milvus   : localhost:19530   （Attu 控制台 http://localhost:8000）")
    say("  日志     : logs\\api.log  logs\\mcp_cls.log  logs\\mcp_monitor.log")
    say("  停止服务 : stop.bat")
    say("=" * 62)
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    say("正在停止 OpsMind ...")
    kill_port(API_PORT, "FastAPI 主服务")
    for name, _script, port in MCP_SERVICES:
        kill_port(port, f"{name} MCP")
        clear_pid(f"mcp_{name}")
    clear_pid("api")
    if args.with_milvus:
        if docker_running():
            say("  正在停止 Milvus 容器 ...")
            res = run(["docker", "compose", *COMPOSE_ARGS, "stop"])
            say("  " + ("Milvus 容器已停止" if res.returncode == 0
                        else (res.stderr or res.stdout).strip()[-300:]))
        else:
            say("  Docker 未运行，跳过 Milvus")
    say("完成。")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    say("=" * 62)
    say("  OpsMind 运行状态")
    say("=" * 62)
    rows = [("FastAPI API", API_PORT)] + [(f"{n} MCP", p) for n, _s, p in MCP_SERVICES] + [("Milvus", MILVUS_PORT)]
    for label, port in rows:
        mark = "运行中" if port_open(port) else "未运行"
        say(f"  {label:<12} 端口 {port:<6} {mark}")
    say(f"  Docker 引擎   {'运行中' if docker_running() else '未运行'}")
    status, body = http_json(API_HEALTH)
    if body:
        data = body.get("data", {})
        say(f"  /health       HTTP {status}  {data.get('status')}  "
            f"milvus={data.get('milvus', {}).get('status')}")
    else:
        say("  /health       不可达")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    for name in ("api", "mcp_cls", "mcp_monitor"):
        path = LOG_DIR / f"{name}.log"
        say(f"\n===== {path} =====")
        if not path.exists():
            say("  (无日志)")
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        say("\n".join(lines[-args.lines:]))
    return 0


IMAGE_REFS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("milvusdb/milvus:v2.5.10", (
        "docker.1panel.live/milvusdb/milvus:v2.5.10",
        "hub.rat.dev/milvusdb/milvus:v2.5.10",
    )),
    ("minio/minio:RELEASE.2023-03-20T20-16-18Z", (
        "docker.1panel.live/minio/minio:RELEASE.2023-03-20T20-16-18Z",
        "docker.m.daocloud.io/minio/minio:RELEASE.2023-03-20T20-16-18Z",
    )),
    ("quay.io/coreos/etcd:v3.5.18", (
        "quay.m.daocloud.io/coreos/etcd:v3.5.18",
        "docker.1panel.live/quay.io/coreos/etcd:v3.5.18",
    )),
    ("zilliz/attu:v2.5", (
        "docker.1panel.live/zilliz/attu:v2.5",
        "docker.m.daocloud.io/zilliz/attu:v2.5",
    )),
)


def cmd_pull_images(args: argparse.Namespace) -> int:
    """按镜像站顺序拉取 Milvus 依赖镜像并重命名为 compose 中使用的名字"""
    if not docker_running():
        say("Docker 引擎未运行，请先打开 Docker Desktop")
        return 1
    ok = True
    for target, candidates in IMAGE_REFS:
        if run(["docker", "image", "inspect", target]).returncode == 0:
            say(f"  已存在  {target}")
            continue
        pulled = False
        for ref in candidates:
            say(f"  拉取 {ref} ...")
            if subprocess.run(["docker", "pull", ref], cwd=str(ROOT)).returncode == 0:
                run(["docker", "tag", ref, target])
                say(f"  完成 {target}  (来源 {ref})")
                pulled = True
                break
            say(f"  失败 {ref}，换下一个镜像站")
        if not pulled:
            say(f"  [错误] 所有镜像站都无法拉取 {target}")
            ok = False
    return 0 if ok else 1


def cmd_upload_docs(args: argparse.Namespace) -> int:
    return 0 if upload_docs(force=True) else 1


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="OpsMind 本地启停控制")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="启动全部依赖与服务")
    p_start.add_argument("--force-docs", action="store_true", help="强制重建知识库向量索引")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="停止服务")
    p_stop.add_argument("--with-milvus", action="store_true", help="同时停止 Milvus 容器")
    p_stop.set_defaults(func=cmd_stop)

    sub.add_parser("status", help="查看运行状态").set_defaults(func=cmd_status)

    p_logs = sub.add_parser("logs", help="查看服务日志")
    p_logs.add_argument("--lines", type=int, default=30)
    p_logs.set_defaults(func=cmd_logs)

    sub.add_parser("upload-docs", help="重建知识库索引").set_defaults(func=cmd_upload_docs)
    sub.add_parser("pull-images", help="经镜像站拉取 Milvus 依赖镜像").set_defaults(func=cmd_pull_images)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
