# 部署指南 —— Linux 服务器（Ubuntu 从零全流程）

> 适用 Ubuntu 22.04 / 24.04（其他发行版命令等价替换）。全程约 15~30 分钟。
> Windows 部署见 [部署指南_Windows.md](部署指南_Windows.md)。以下所有命令以普通用户执行，需要提权处已带 `sudo`。

---

## 1. 系统基础工具

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git build-essential ca-certificates gnupg
```

## 2. 安装 Python 3.12

```bash
# Ubuntu 24.04 官方源自带 3.12：
sudo apt install -y python3.12 python3.12-venv

# Ubuntu 22.04 需 deadsnakes PPA：
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update && sudo apt install -y python3.12 python3.12-venv

python3.12 --version    # 确认 Python 3.12.x
```

## 3. 安装 uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc        # 或重开终端使 PATH 生效
uv --version
```

> 国内网络加速（可选，写入 ~/.bashrc 持久化）：
> `export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple`

## 4. 安装 Docker Engine + Compose

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker $USER && newgrp docker   # 免 sudo（需重新登录生效）
docker compose version                            # 确认 compose 插件
```

拉取镜像缓慢时用加速地址（**不改任何 Docker 配置**）：

```bash
docker pull docker.m.daocloud.io/library/postgres:16
docker tag  docker.m.daocloud.io/library/postgres:16 postgres:16
docker pull docker.m.daocloud.io/minio/minio:latest
docker tag  docker.m.daocloud.io/minio/minio:latest minio/minio:latest
docker pull docker.m.daocloud.io/redis/redis-stack-server:7.4-v0
docker tag  docker.m.daocloud.io/redis/redis-stack-server:7.4-v0 redis/redis-stack-server:7.4-v0
```

## 5. 安装 Node.js 20+

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v && npm -v
```

> 国内 npm 镜像（可选）：`npm config set registry https://registry.npmmirror.com`

## 6. 获取项目并启动基础设施

```bash
# 方式一：git 克隆（仓库地址替换为自己的）
git clone https://github.com/<你的用户名>/spray-qc-agent.git
cd spray-qc-agent

# 方式二：本地打包上传后解压进入项目根目录

docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml ps    # postgres / redis / minio 三项 healthy
```

## 7. 后端初始化

```bash
cd backend
uv sync                                          # 自动创建 .venv（识别 3.12）
cp .env.example .env
nano .env                                        # 填 LLM_PROVIDER / QWEN_API_KEY / QWEN_BASE_URL
#   离线演示 → LLM_PROVIDER=mock；公网 DashScope → qwen + key；
#   专属推理端点(*.maas.aliyuncs.com) → qwen + key + 对应 QWEN_BASE_URL（否则 401）

uv run python scripts/init_db.py                 # 迁移 + 种子（3 账号 / 5 工件及标准）
uv run python scripts/init_buckets.py            # MinIO 私有桶
uv run python scripts/seed_mock_data.py          # Mock 场景 + 工艺知识
uv run python scripts/check_providers.py         # LLM 连通性自检（三项 ✅）

# 前台试运行（确认无误 Ctrl+C，换第 8 步常驻）：
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 8. 后端常驻（systemd）

```bash
sudo tee /etc/systemd/system/spray-qc.service > /dev/null <<'EOF'
[Unit]
Description=Spray QC Agent Backend
After=network.target docker.service

[Service]
Type=simple
User=<你的用户名>
WorkingDirectory=/home/<你的用户名>/spray-qc-agent/backend
ExecStart=/home/<你的用户名>/spray-qc-agent/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now spray-qc
sudo systemctl status spray-qc          # active (running) 即成功
journalctl -u spray-qc -f               # 实时日志（Ctrl+C 退出查看）
```

## 9. 前端构建与 Nginx 托管（生产推荐）

```bash
cd frontend
npm install
npm run build                            # 产物 dist/
```

```bash
sudo apt install -y nginx
sudo tee /etc/nginx/sites-available/spray-qc > /dev/null <<'EOF'
server {
    listen 80;
    server_name _;

    # 前端静态资源
    root /home/<你的用户名>/spray-qc-agent/frontend/dist;
    index index.html;
    location / { try_files $uri $uri/ /index.html; }

    # 后端 API 反向代理（含 SSE 流式）
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_buffering off;             # SSE 必需：关闭缓冲让 token 流实时到达
        proxy_read_timeout 300s;         # 检测含多次 LLM 调用，放宽读超时
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/spray-qc /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

> dist 路径权限：Nginx 运行用户需可读用户家目录下的文件，若 403 可 `chmod 755 /home/<你的用户名>` 或把 dist 拷到 `/var/www/spray-qc` 并同步修改配置中的 root。

## 10. 防火墙与验收

```bash
sudo ufw allow 80/tcp
sudo ufw allow 22/tcp
sudo ufw enable

curl http://127.0.0.1:8000/health        # {"status":"ok",...}
浏览器访问 http://<服务器IP>/              # 登录页 → 演示账号进入
```

演示账号：`operator/Operator@123`、`engineer/Engineer@123`、`admin/Admin@123`。

---

## 附：运维速查

| 操作 | 命令 |
| --- | --- |
| 后端重启 / 停止 | `sudo systemctl restart|stop spray-qc` |
| 后端日志 | `journalctl -u spray-qc -f` |
| 容器状态 / 重启 | `docker compose -f deploy/docker-compose.yml ps / restart` |
| 彻底重置数据 | `docker compose -f deploy/docker-compose.yml down -v` 后重跑第 7 步初始化 |
| 更新代码后 | `git pull` → `cd backend && uv sync && alembic upgrade head` → `sudo systemctl restart spray-qc` → （前端有改动）`cd frontend && npm run build` |
| 数据库迁移新增 | `cd backend && uv run alembic upgrade head` |

> 公网安全提醒：`deploy/docker-compose.yml` 内为开发演示密码（PG/MinIO），公网部署请用环境变量覆盖并只监听内网端口；MinIO 控制台（9001）与 PG（5432）不要暴露公网。
