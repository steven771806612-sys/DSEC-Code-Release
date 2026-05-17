# DSEC AI Case Review System

DJI 安防案例 AI 评审平台，包含 FastAPI 后端与 React + Vite 前端。

## 项目结构

```text
.
├── dsec-backend/               # FastAPI, SQLAlchemy, Alembic, pytest
│   ├── app/                    # 应用源码
│   ├── alembic/                # 数据库迁移脚本
│   ├── tests/                  # 单元测试
│   ├── seed.py                 # 数据库初始化脚本（测试账号 + 默认 Rubric）
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
├── dsec-frontend/              # React, TypeScript, Vite, ESLint
└── DJI_AI_Case_Review_System_Design.md
```

## 推荐运行环境

- Python 3.12
- Node.js 20
- npm 10
- PostgreSQL 16 + pgvector
- MinIO / S3

## 快速开始

### 1. 启动后端

```bash
cd dsec-backend
cp .env.example .env
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端默认地址：`http://localhost:8000`

### 2. 初始化数据库并写入种子数据

**前提**：数据库已启动，且 `alembic upgrade head` 已执行完毕。

```bash
cd dsec-backend
# 本地 Docker 环境（默认连接 localhost:5432）
python seed.py

# 指定远程数据库
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dsec python seed.py

# Railway 部署环境
railway run python seed.py
```

执行成功后将自动创建以下账号：

| 角色 | 邮箱 | 密码 | 登录后跳转 |
|------|------|------|------------|
| `admin` | admin@dsec.com | `Admin1234!` | `/ops/dashboard` |
| `dji_se` | dji@dsec.com | `DjiSE1234!` | `/dji` |
| `platform_reviewer` | reviewer@dsec.com | `Review1234!` | `/reviewer` |
| `agent` | agent@partner.com | `Agent1234!` | `/agent` |

同时初始化：
- **默认 Rubric v1.0**（4 维度，各 25 分）
- **默认 System Prompt v1.0**（AI 评审引导词）

> ⚠️ seed.py 使用 `INSERT … WHERE NOT EXISTS` 语义，重复执行不会覆盖已有数据，可安全多次运行。

### 3. 启动前端

```bash
cd dsec-frontend
cp .env .env.local 2>/dev/null || true
npm install
npm run dev
```

前端默认地址：`http://localhost:5173`

> 如果后端地址变化，请同步更新 `dsec-frontend/.env` 中的 `VITE_API_BASE_URL`。

## Docker 本地开发

```bash
cd dsec-backend
cp .env.example .env
docker compose up --build
```

服务说明：

- API: `http://localhost:8000`
- API Docs (Swagger): `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`

数据库启动后，执行迁移与种子数据：

```bash
# 在容器内执行迁移
docker compose exec api alembic upgrade head

# 写入种子数据
docker compose exec api python seed.py
```

## 前台页面路由

| 角色 | 登录账号 | 路由入口 |
|------|----------|----------|
| 管理员 | admin@dsec.com | `/ops/dashboard` |
| DJI 工程师 | dji@dsec.com | `/dji` |
| 平台审核员 | reviewer@dsec.com | `/reviewer` |
| 渠道商 | agent@partner.com | `/agent` |

所有用户登录入口：`/login`

## 测试与质量检查

### 后端测试

```bash
cd dsec-backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install aiosqlite
pytest -q
```

说明：测试默认使用 SQLite 内存库，并在测试侧兼容 PostgreSQL `JSONB` 字段。

### 前端质量检查

```bash
cd dsec-frontend
npm install
npm run lint
npm run build
```

## 已处理的关键工程问题

- 修复 FastAPI 依赖注入冲突，应用可正常导入与测试。
- 修复前端类型问题，`npm run lint` 已通过。
- 修复前端依赖重装后的构建问题，`npm run build` 已通过。
- 修复测试环境下 PostgreSQL `JSONB` 与 SQLite 不兼容的问题。
- 修复 `passlib + bcrypt` 兼容性问题，补充 `bcrypt==3.2.2`。
- 修复 422 弃用状态码 warning，改用 `HTTP_422_UNPROCESSABLE_CONTENT`。

## CI

仓库已补充 GitHub Actions 工作流：

- 后端：安装依赖并运行 `pytest`
- 前端：安装依赖并执行 `lint` + `build`

工作流文件路径：`.github/workflows/ci.yml`

## 交付建议

建议提交仓库时不要包含以下目录：

- `dsec-backend/.venv`
- `dsec-frontend/node_modules`
- `dsec-frontend/dist`
- `__pycache__`

这样可以避免平台污染、包体膨胀和依赖失真。
