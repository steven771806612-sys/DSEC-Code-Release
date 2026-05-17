# DSEC AI Case Review System

DJI 安防案例 AI 评审平台，包含 FastAPI 后端与 React + Vite 前端。

## 项目结构

```text
.
├── dsec-backend/     # FastAPI, SQLAlchemy, Alembic, pytest
├── dsec-frontend/    # React, TypeScript, Vite, ESLint
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

### 2. 启动前端

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
- PostgreSQL: `localhost:5432`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`

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
