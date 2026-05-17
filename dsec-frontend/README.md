# DSEC Frontend

DSEC AI Case Review System 前端项目，基于 React + TypeScript + Vite 构建。

## 技术栈

- React 19
- TypeScript
- Vite 8
- TanStack Query
- React Hook Form
- Zustand
- Tailwind CSS
- ESLint

## 本地启动

```bash
npm install
npm run dev
```

默认开发地址：`http://localhost:5173`

## 环境变量

`.env`

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 质量检查

```bash
npm run lint
npm run build
```

## 角色页面

- Agent：案例提交、编辑、查看
- Platform Reviewer：平台复核
- DJI SE：终审
- Admin/Ops：Dashboard、Prompt 管理、审计与分歧分析
