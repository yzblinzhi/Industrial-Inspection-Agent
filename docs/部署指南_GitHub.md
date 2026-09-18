# 部署指南 —— GitHub 上传与维护（自用）

> 用途：把本项目 V1.1 推上 GitHub 并日常维护。**先做完第 1 节隐私规避，再做上传**。

---

## 1. 隐私规避清单（上传前必做，逐项打勾）

- [ ] **`.gitignore` 已包含**（本项目已配好，检查即可）：
  - `backend/.env`（**真实密钥所在地，绝不能上传**）
  - `.venv/`、`node_modules/`、`dist/`、`__pycache__/`、`.zcode/`（本地开发内部文件）
- [ ] **暂存区验证**（git init + add 之后、commit 之前执行）：
  ```bash
  git init
  git add .
  git status --porcelain | grep -i "\.env"
  # 只允许出现 backend/.env.example；出现 backend/.env 立即：
  #   git rm --cached backend/.env && git commit 前重查
  ```
- [ ] **`.env.example` 无真实密钥**：只有 `sk-请替换为你的通义千问APIKey` 占位符；
- [ ] **截图自查**：`docs/界面截图/` 内图片若含真实批次号、测试对话内容、内部主机名等不想公开的信息，先替换或打码；
- [ ] **docker-compose 演示密码**：仓库内保留演示值可以接受，但公网部署时必须覆盖（Linux 指南末尾已提醒）；
- [ ] **误提交应急**：一旦真实 key 曾被 commit/push，立即到阿里云百炼控制台**吊销该 key** 并生成新的（仅删除提交不能消除 GitHub 缓存与 fork）。

## 2. 首次上传

### 方式一：网页建仓（推荐第一次用）

```bash
cd F:\Agent_Project\Spraying_agent_Project

git init
git add .
# ↓ 第 1 节的暂存区验证在这里做
git commit -m "release: 喷涂质检智能体 V1.1"

# 到 https://github.com/new 网页创建空仓库（名字如 spray-qc-agent，
# 不要勾选 README/.gitignore/license 任何初始化！），然后：
git remote add origin https://github.com/<你的用户名>/spray-qc-agent.git
git branch -M main
git push -u origin main        # 首次会弹浏览器登录 GitHub 授权
```

### 方式二：gh CLI 一条龙

```bash
# 安装 gh：winget install GitHub.cli  （或 https://cli.github.com/）
gh auth login                   # 按提示浏览器授权
cd F:\Agent_Project\Spraying_agent_Project
git init && git add . && git commit -m "release: V1.1"
gh repo create spray-qc-agent --public --source=. --remote=origin --push
```

### 推送后自查（1 分钟）

- 仓库首页应显示 README（门面+截图）；
- 点开 `backend/` 目录：**没有 `.env` 文件**（只有 `.env.example`）；
- GitHub 仓库页 → Security → Code scanning 无密钥告警。

## 3. 打版本标签

```bash
git tag -a v1.1 -m "V1.1: 复核工单化 + 检测数据库 + 智能工件解析"
git push origin v1.1
```

## 4. 日常更新（记住这四条循环）

```bash
git add .                        # 1 收集改动
git commit -m "feat: 修了xx"     # 2 本地存档（此时 GitHub 还不知道）
git push                         # 3 上传（GitHub 才更新）
git log --oneline -5             # 4 查看最近提交（可选）
```

要点：
- **没 push 的改动 GitHub 完全不知道**；commit 只存在本地；
- 只想本地存档不想公开时，停在 commit 即可；
- 提交信息建议 `feat:`新功能 / `fix:`修bug / `docs:`文档 / `refactor:`重构 开头。

## 5. 多机 / 协作场景

```bash
# 在另一台电脑首次获取：
git clone https://github.com/<你的用户名>/spray-qc-agent.git
# 按 docs/部署指南_Windows.md 或 _Linux.md 初始化（.env 要自己新建）

# 别的电脑（或 GitHub 网页）改过代码后，回本机先拉再推：
git pull
git add . && git commit -m "..." && git push

# push 被拒绝（远程有新提交）：
git pull --rebase && git push
```

## 6. 常用排查

| 现象 | 处理 |
| --- | --- |
| push 要求登录但弹窗失败 | 安装并 `gh auth login`，或改用 SSH key（`ssh-keygen -t ed25519` 后把公钥加到 GitHub Settings→SSH keys，remote 改 `git@github.com:...`） |
| 误把 backend/.env 提交了（还没 push） | `git rm --cached backend/.env && git commit --amend --no-edit`；**已 push 则吊销 key** |
| 想忽略的文件已被跟踪 | `git rm --cached <路径>`（保留本地文件）后 commit；.gitignore 只对未跟踪文件生效 |
| 仓库太大推不动 | 确认 `node_modules/`、`.venv/`、`dist/` 没被跟踪：`git ls-files | grep -E "node_modules|\.venv"` 应为空 |
