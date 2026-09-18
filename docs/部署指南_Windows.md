# 部署指南 —— Windows

> 本文档分两部分：**A. 日常启动**（机器已配好环境，每次开机后拉起系统看这里）；**B. 从零部署**（一台全新的 Windows 机器，从安装环境到跑通全流程看这里）。
> Linux 服务器部署见 [部署指南_Linux.md](部署指南_Linux.md)；GitHub 上传见 [部署指南_GitHub.md](部署指南_GitHub.md)。

---

## A. 日常启动（自用速查）

### 前置检查（30 秒）

```bash
# Docker Desktop 必须处于运行状态（任务栏鲸鱼图标）
docker ps                                       # 能列出容器即正常
uv --version                                    # 或全路径 %USERPROFILE%\.local\bin\uv.exe
node -v                                         # ≥ v20
```

> 若 `uv` 提示找不到命令：它装在 `C:\Users\<你>\.local\bin\uv.exe`，用全路径调用，或把该目录加入用户 PATH（一次配好永久生效）。

### 第 1 步：起基础设施（三容器）

```bash
cd F:\Agent_Project\Spraying_agent_Project      # 换成你的项目路径
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml ps  # postgres / redis / minio 三项 healthy
```

### 第 2 步：起后端（8000）

```bash
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
# 看到 "服务就绪 | CV=mock RAG=mock LLM=qwen" 即成功（LLM 取决于 .env）
# 健康检查（新开终端）：curl http://127.0.0.1:8000/health
```

### 第 3 步：起前端（5173）

```bash
cd frontend
npm run dev      # 浏览器打开 http://localhost:5173
```

### 演示账号

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| `operator` | `Operator@123` | 操作工 |
| `engineer` | `Engineer@123` | 工艺员 |
| `admin` | `Admin@123` | 管理员 |

### 停止

- 后端 / 前端：各自终端 `Ctrl+C`；
- 容器：`docker compose -f deploy/docker-compose.yml down`（**不要加 `-v`**，加 `-v` 会删除数据库全部数据！）；想彻底重置数据才用 `down -v` 然后重跑 B 部分第 6 步初始化。

### 常用验证命令

```bash
cd backend
uv run pytest                                  # 单元测试（离线，23 个）
uv run python scripts/check_providers.py       # LLM 连通性诊断（密钥脱敏）
CV_MOCK_MODE=match LLM_PROVIDER=mock uv run python scripts/run_eval.py    # 评测回归
CV_MOCK_MODE=match LLM_PROVIDER=mock uv run python scripts/smoke_api.py   # API 冒烟（打 8000）
```

> 上面前缀写法适用于 **Git Bash**；**PowerShell** 用：`$env:LLM_PROVIDER="mock"; $env:CV_MOCK_MODE="match"; uv run python scripts/run_eval.py`；**CMD** 用：`set LLM_PROVIDER=mock && set CV_MOCK_MODE=match && uv run ...`。

---

## B. Windows 从零部署（全新机器）

### 1. 安装 Docker Desktop

1. 下载：https://www.docker.com/products/docker-desktop/ （Windows 版安装器）；
2. 安装时勾选 **Use WSL 2 instead of Hyper-V**（推荐）；
3. 安装完**重启电脑**，启动 Docker Desktop，等鲸鱼图标变为运行状态；
4. 验证：`docker --version` 与 `docker compose version`。

> 若提示需要启用 WSL2：管理员 PowerShell 执行 `wsl --install` 后重启。
> 拉取镜像慢见第 5 步的加速说明。

### 2. 安装 Python 3.12

方式一（推荐，winget）：

```powershell
winget install Python.Python.3.12
```

方式二：官网 https://www.python.org/downloads/ 下载 3.12.x 安装器，**勾选 "Add Python to PATH"**。

验证：`python --version` → `Python 3.12.x`。
（其实 uv 也能自动下载管理 3.12，见下一步；本机有 3.12 只是为了保险。）

### 3. 安装 uv

```powershell
# PowerShell：
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

验证（新开终端）：`uv --version`。默认装在 `%USERPROFILE%\.local\bin\uv.exe`。

### 4. 安装 Node.js 20+

```powershell
winget install OpenJS.NodeJS.LTS
```

或官网 https://nodejs.org/ 下载 LTS 安装。验证：`node -v`、`npm -v`。
国内加速 npm：`npm config set registry https://registry.npmmirror.com`。

### 5. 获取项目并起容器

```bash
# 方式一：git 克隆（需先 git config --global user.name/email）
git clone https://github.com/<你的用户名>/spray-qc-agent.git
cd spray-qc-agent

# 方式二：直接拷贝/解压项目文件夹后进入

docker compose -f deploy/docker-compose.yml up -d
```

Docker Hub 拉取失败（超时）时，用镜像加速地址拉取后打回标准 tag（**不改任何 Docker 配置**）：

```bash
docker pull docker.m.daocloud.io/library/postgres:16
docker tag  docker.m.daocloud.io/library/postgres:16 postgres:16
docker pull docker.m.daocloud.io/minio/minio:latest
docker tag  docker.m.daocloud.io/minio/minio:latest minio/minio:latest
docker pull docker.m.daocloud.io/redis/redis-stack-server:7.4-v0
docker tag  docker.m.daocloud.io/redis/redis-stack-server:7.4-v0 redis/redis-stack-server:7.4-v0
# 然后重新 up -d
```

### 6. 后端初始化（一次性）

```bash
cd backend
uv sync    # 自动创建 backend\.venv（识别 .python-version 的 3.12）

copy .env.example .env     # CMD；PowerShell: Copy-Item .env.example .env
notepad .env               # 按需修改：
#   离线演示      → LLM_PROVIDER=mock（无需密钥，全链路可跑）
#   通义千问公网  → LLM_PROVIDER=qwen + QWEN_API_KEY=sk-xxx（BASE_URL 保持默认）
#   专属推理端点  → LLM_PROVIDER=qwen + QWEN_API_KEY=sk-ws-xxx
#                    + QWEN_BASE_URL=https://xxxx.maas.aliyuncs.com/compatible-mode/v1
#                    （key 与端点必须匹配，否则 401）

uv run python scripts/init_db.py          # 建表迁移 + 种子（3 账号/5 工件/标准）
uv run python scripts/init_buckets.py     # MinIO 两个私有桶
uv run python scripts/seed_mock_data.py   # Mock 检测场景 + 工艺知识语料
uv run python scripts/check_providers.py  # LLM 连通性自检（三项 ✅ 才算配好）
```

### 7. 启动与验证

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000     # 后端
# 新终端：
cd ../frontend
npm install     # 首次
npm run dev     # 前端 http://localhost:5173
```

用演示账号登录，输入 `检测立柱 CL-ZH02-B，批次 B2026-09-01` 走一遍检测 → 全流程即部署成功。

### 8. Windows 特有坑（本项目实测踩过）

| 现象 | 原因与处理 |
| --- | --- |
| alembic 报 `UnicodeDecodeError: gbk` | ini 文件含中文注释在 GBK 环境解析失败——本项目 ini 已全 ASCII；自己新建配置文件时注意 |
| bcrypt 报 `password cannot be longer than 72 bytes` | passlib 与 bcrypt 5.x 不兼容——本项目已锁 `bcrypt<4.1`（pyproject），勿手动升级 |
| 8000/5173 端口被占 | `netstat -ano | findstr :8000` 找 PID → 任务管理器结束，或 `taskkill /F /PID <pid>` |
| Redis 报 `Cannot create index on db != 0` | `.env` 两个 REDIS_DSN 必须都是 `/0`（RediSearch 限制） |
| 后台起的 uvicorn 关不掉还占端口 | 包装进程退了子进程还活着：`netstat` 找 PID 后 `taskkill /F`；测试实例（如 8001）用完即清 |
| 前端改代码页面行为不变 | Vite 热更新偶发失效：重启 `npm run dev`，必要时加 `--force` |
| 时间显示与手表差几小时 | 系统时钟不准（同时影响浏览器与数据库）：设置 → 时间和语言 → 开启"自动设置时间" |

---

## 附：端口与数据速查

| 端口 | 服务 | 说明 |
| --- | --- | --- |
| 8000 | 后端 API（生产，按 .env 的 LLM 模式） | 常驻 |
| 5173 | 前端 dev（/api 代理到 8000） | 开发期 |
| 5432 / 6379 / 9000 / 9001 | PG / Redis / MinIO API / MinIO 控制台 | 容器 |

| 数据 | 位置 | 清空方式 |
| --- | --- | --- |
| 业务数据（检测/复核/用户） | PG 卷 `pg_data` | `docker compose down -v` 后重跑 init_db |
| 会话状态（24h TTL 自动过期） | Redis 卷 | 同上 / 等待过期 |
| 图片与报告 | MinIO 卷 `minio_data` | 同上 |
