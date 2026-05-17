# DJI AI Case Review System — Full System Design Spec

---

## 0. Executive Summary

### 系统目标

构建一个面向 DJI 安防生态的 **AI 辅助案例评审平台**，实现代理商提交安防集成案例后，经由 AI 预审、平台复核、DJI 终审的多级评审流程，最终沉淀高质量案例知识库，持续提升 AI 评审准确率。

### 核心问题

| 问题 | 现状 | 目标 |
|---|---|---|
| 评审标准不一致 | 依赖人工经验，评分主观 | AI 基于 Rubric 知识库输出结构化评分 |
| 评审周期长 | 平均 5-7 个工作日 | AI 预审压缩至分钟级，人工只审异常 |
| 知识无法复用 | 优质案例散落各处 | 向量化沉淀，RAG 检索驱动新案例评审 |
| 分歧无法追踪 | AI 与人工判断差异不可见 | Disagreement Engine 记录并生成训练信号 |

### AI+RAG 解决方案

```
Agent 提交案例
    → AI (RAG + LLM) 按 Rubric 逐页评审，输出结构化评分
    → Platform Reviewer 复核 AI 结论，可覆盖
    → DJI SE 终审，结论为 Ground Truth
    → 审毕知识入库，驱动下一轮 RAG 质量提升
```

### 系统边界

- **IN SCOPE**: 案例提交、AI 评审、人工评审、知识管理、通知、运维面板
- **OUT OF SCOPE**: DJI 内部 ERP/CRM 集成、移动端 App、实时视频评审
- **假设**: 初期单租户 DJI 内部部署，后续扩展多租户 SaaS

---

## 1. System Architecture Overview

### 1.1 High Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend Layer                          │
│   Agent Portal │ Reviewer Dashboard │ DJI SE Console │ Ops  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS / REST + WebSocket
┌──────────────────────────▼──────────────────────────────────┐
│                   API Gateway (FastAPI)                       │
│   Auth Middleware │ RBAC Guard │ Rate Limiter │ Request Log  │
└──┬──────────┬─────────────┬───────────────┬─────────────────┘
   │          │             │               │
   ▼          ▼             ▼               ▼
Case       Review        RAG            Ops
Service    Service       Service        Service
   │          │             │               │
   └──────────┴──────┬──────┴───────────────┘
                     │
         ┌───────────▼───────────┐
         │   PostgreSQL (主数据库) │
         │   + pgvector 扩展      │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   S3 / MinIO (文件存储) │
         │   (PDF, 附件, 图片)    │
         └───────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   OpenAI API           │
         │   (Embedding + LLM)   │
         └───────────────────────┘
```

**各层职责:**

| Layer | 技术选型 | 职责 |
|---|---|---|
| Frontend | React + TypeScript + Tailwind | 案例提交、评审操作、运维面板 |
| API Layer | FastAPI + Pydantic v2 | 路由、认证、业务编排 |
| Domain Services | Python 模块化 | Case/Review/RAG/Ops 独立服务模块 |
| RAG Engine | LangChain + OpenAI | 检索增强评审推理 |
| Vector DB | pgvector (PostgreSQL) | 嵌入存储与相似检索 |
| Notification | SMTP + PDF (WeasyPrint) | 邮件与报告分发 |
| Ops Platform | FastAPI Admin + 自定义面板 | 知识管理、监控、审计 |

### 1.2 Deployment Architecture

```
Railway Platform
├── web service (FastAPI)         ← 主应用，单进程 + uvicorn
├── Postgres addon                ← pgvector 扩展启用
└── 环境变量管理 (Railway Env)

外部依赖:
├── OpenAI API                    ← Embedding (text-embedding-3-small) + GPT-4o
└── AWS S3 / Cloudflare R2        ← 附件对象存储

本地开发:
└── Docker Compose
    ├── app (FastAPI + hot-reload)
    ├── db  (postgres:16 + pgvector)
    ├── redis (optional, 缓存/队列)
    └── minio (S3 本地模拟)
```

---

## 2. Identity & Access Control Layer

### 2.1 Entity Model

```python
class Org(Base):
    id: UUID
    name: str
    region: str                    # APAC / EMEA / AMER
    tier: str                      # gold / silver / bronze
    is_active: bool
    created_at: datetime

class Department(Base):
    id: UUID
    org_id: UUID                   # FK → Org (DJI内部部门)
    name: str
    is_dji_internal: bool

class User(Base):
    id: UUID
    email: str                     # unique
    hashed_password: str
    full_name: str
    org_id: UUID                   # FK → Org
    department_id: Optional[UUID]  # FK → Department (DJI内部)
    role: RoleEnum                 # 见 2.2
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime

class Role(Base):
    # 枚举实现，见 2.2
    pass
```

### 2.2 RBAC Model

| Role | 标识 | 权限范围 |
|---|---|---|
| **Agent** | `agent` | 提交/编辑自己 Org 的案例；查看自己的评审结果 |
| **Platform Reviewer** | `platform_reviewer` | 查看所有已提交案例；覆写 AI 评审；不可修改 DJI 评审 |
| **DJI SE** | `dji_se` | 终审所有案例；查看全部数据；结论即 Ground Truth |
| **Admin** | `admin` | 用户管理；Rubric 知识库管理；系统配置；Ops 平台完整访问 |

**权限矩阵:**

```
操作                    Agent   Platform  DJI SE  Admin
─────────────────────────────────────────────────────
创建案例                  ✓        ✗        ✗       ✓
编辑草稿案例              ✓(own)   ✗        ✗       ✓
提交案例                  ✓(own)   ✗        ✗       ✓
查看AI评审结果            ✓(own)   ✓        ✓       ✓
平台复核/覆写AI           ✗        ✓        ✓       ✓
DJI终审                  ✗        ✗        ✓       ✓
管理Rubric知识库          ✗        ✗        ✗       ✓
查看Disagreement报告      ✗        ✗        ✓       ✓
访问Ops平台               ✗        ✗(部分)  ✓(部分) ✓
```

### 2.3 Data Isolation Rules

**Org-level isolation:**
- Agent 只能访问自己 `org_id` 下的案例，API 层通过 `current_user.org_id` 自动注入过滤条件
- 所有 Case 查询默认附加 `WHERE org_id = :current_org_id`（非 DJI 角色）

**Case-level scope control:**
- `CaseVersion` 仅案例所属 Org 成员和 Reviewer 可访问
- AI 评审中间结果（Evaluation Trace）仅 DJI SE 和 Admin 可见
- 附件 S3 URL 使用短时签名（15 分钟有效），服务端验证用户权限后生成

---

## 3. Case Domain Design

### 3.1 Core Entity Model

```python
class Case(Base):
    __tablename__ = "cases"

    id: UUID
    org_id: UUID                       # FK → Org
    created_by: UUID                   # FK → User (Agent)
    title: str
    industry: IndustryEnum             # retail / logistics / manufacturing / ...
    region: str
    status: CaseStatusEnum             # 见 3.3
    current_version_id: Optional[UUID]
    rubric_version: str                # e.g. "v2.1"
    tags: List[str]                    # JSONB
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime]
    closed_at: Optional[datetime]

class CaseVersion(Base):
    __tablename__ = "case_versions"

    id: UUID
    case_id: UUID                      # FK → Case
    version_number: int                # 1, 2, 3...
    submitted_by: UUID                 # FK → User
    change_summary: str
    is_current: bool
    created_at: datetime

class CasePage(Base):
    __tablename__ = "case_pages"
    # Page = AI 评审最小单元（见 3.2）

    id: UUID
    case_version_id: UUID              # FK → CaseVersion
    page_number: int
    page_type: PageTypeEnum            # overview / architecture / deployment / results / appendix
    title: str
    content_text: str                  # 提取的纯文本（供 LLM）
    content_html: Optional[str]        # 富文本展示
    embedding_id: Optional[UUID]       # FK → pgvector 记录
    word_count: int
    has_images: bool
    created_at: datetime

class Attachment(Base):
    __tablename__ = "attachments"

    id: UUID
    case_id: UUID                      # FK → Case
    case_version_id: UUID              # FK → CaseVersion
    file_name: str
    file_type: str                     # pdf / docx / png / jpg
    s3_key: str                        # S3 对象键
    file_size_bytes: int
    uploaded_by: UUID                  # FK → User
    is_primary: bool                   # 主文档标志
    created_at: datetime
```

### 3.2 Page-Level Design Principle

**Page = AI 评审的最小推理单元**

```
整体案例
└── CaseVersion (版本快照)
    ├── Page 1: Project Overview      → AI评分维度: 背景清晰度、商业价值
    ├── Page 2: Architecture Design   → AI评分维度: 技术选型、系统集成
    ├── Page 3: Deployment Details    → AI评分维度: 实施方案、可复制性
    ├── Page 4: Results & ROI         → AI评分维度: 数据支撑、效果量化
    └── Page 5: Appendix              → AI评分维度: 完整性、附件质量
```

**设计理由:**
1. 分页可并发评审，降低单次 LLM 上下文长度
2. 页级评分可精准定位问题，比案例级评分更具指导价值
3. 页级 Embedding 检索比整体案例检索更精确

### 3.3 Case Lifecycle

```
DRAFT ──────── 提交 ──────────► SUBMITTED
                                    │
                              AI评审触发 (async)
                                    │
                                    ▼
                              AI_REVIEWED ──── AI评审失败 ──► DRAFT (with error)
                                    │
                            Platform Reviewer分配
                                    │
                                    ▼
                           PLATFORM_REVIEWED ─── 驳回 ──► DRAFT
                                    │
                              路由至DJI SE
                                    │
                                    ▼
                            DJI_REVIEWED
                           ╱                  ╲
                     APPROVED              REJECTED
                          │
                    知识入库 + 通知
```

**状态说明:**

| 状态 | 含义 | 可执行操作 |
|---|---|---|
| `DRAFT` | 草稿，Agent 可编辑 | 编辑、提交、删除 |
| `SUBMITTED` | 已提交，等待AI | 撤回（5分钟内） |
| `AI_REVIEWED` | AI评审完成 | Platform Reviewer 介入 |
| `PLATFORM_REVIEWED` | 平台复核完成 | DJI SE 介入 |
| `DJI_REVIEWED` | DJI审毕 | 等待最终决定 |
| `APPROVED` | 终审通过 | 知识入库、生成报告 |
| `REJECTED` | 终审拒绝 | Agent查看反馈、重新提交 |

---

## 4. Review & Workflow Engine

### 4.1 Review Types

| 类型 | 执行者 | 输出 | 可覆写 |
|---|---|---|---|
| **AI Review** | RAG+LLM (自动) | 结构化评分 + 问题列表 + 建议 | 可被 Platform 覆写 |
| **Platform Review** | Platform Reviewer | 确认/修改AI结论 + 补充意见 | 可被 DJI 覆写 |
| **DJI Review** | DJI SE | 最终裁决 + 详细反馈 | 不可覆写（Ground Truth）|

### 4.2 Review Task System

```python
class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: UUID
    case_id: UUID
    review_type: ReviewTypeEnum        # ai / platform / dji
    assigned_to: Optional[UUID]        # NULL表示AI
    status: TaskStatusEnum             # pending / in_progress / completed / skipped
    priority: int                      # 1-5
    due_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    sla_breached: bool

class Review(Base):
    __tablename__ = "reviews"

    id: UUID
    case_id: UUID
    case_version_id: UUID
    review_task_id: UUID
    reviewer_id: Optional[UUID]        # NULL = AI
    review_type: ReviewTypeEnum
    overall_score: Optional[float]     # 0-100
    dimension_scores: dict             # JSONB {dimension: score}
    issues: List[dict]                 # JSONB [{severity, page, description}]
    recommendations: List[str]         # JSONB
    decision: DecisionEnum             # approve / reject / revise / pending
    confidence: Optional[float]        # AI置信度 0-1
    is_override: bool                  # 是否覆写了上一层评审
    override_reason: Optional[str]
    raw_llm_output: Optional[dict]     # JSONB 存储完整LLM响应
    created_at: datetime
    updated_at: datetime
```

**Assignment Engine 路由规则:**

```python
def assign_reviewer(case: Case, review_type: ReviewTypeEnum) -> Optional[User]:
    if review_type == ReviewTypeEnum.AI:
        return None  # 自动执行

    if review_type == ReviewTypeEnum.PLATFORM:
        # 按 industry 匹配专业 reviewer
        # 按当前工作负荷轮询分配
        reviewers = get_available_reviewers(
            role=RoleEnum.PLATFORM_REVIEWER,
            industry=case.industry,
            region=case.region
        )
        return min(reviewers, key=lambda r: r.active_task_count)

    if review_type == ReviewTypeEnum.DJI:
        # 按 region 分配 DJI SE
        dji_ses = get_available_dji_se(region=case.region)
        return min(dji_ses, key=lambda r: r.active_task_count)
```

### 4.3 Workflow State Machine

```python
# 状态转换规则（卫语句模式）
TRANSITIONS = {
    CaseStatus.DRAFT: {
        "submit": CaseStatus.SUBMITTED,
    },
    CaseStatus.SUBMITTED: {
        "ai_complete": CaseStatus.AI_REVIEWED,
        "ai_fail": CaseStatus.DRAFT,
        "agent_withdraw": CaseStatus.DRAFT,  # 5min window
    },
    CaseStatus.AI_REVIEWED: {
        "platform_complete": CaseStatus.PLATFORM_REVIEWED,
    },
    CaseStatus.PLATFORM_REVIEWED: {
        "platform_reject": CaseStatus.DRAFT,
        "dji_complete": CaseStatus.DJI_REVIEWED,
    },
    CaseStatus.DJI_REVIEWED: {
        "approve": CaseStatus.APPROVED,
        "reject": CaseStatus.REJECTED,
    },
}

def transition(case: Case, event: str, actor: User) -> Case:
    allowed = TRANSITIONS.get(case.status, {})
    if event not in allowed:
        raise InvalidTransitionError(f"{case.status} → {event} not allowed")
    validate_actor_permission(actor, event, case)  # RBAC guard
    new_status = allowed[event]
    case.status = new_status
    emit_event(CaseStatusChangedEvent(case_id=case.id, event=event, actor=actor))
    return case
```

**事件触发器:**

| 事件 | 触发动作 |
|---|---|
| `SUBMITTED` | 异步触发 AI Review Task |
| `AI_REVIEWED` | 分配 Platform Review Task；通知 Reviewer |
| `PLATFORM_REVIEWED` | 分配 DJI Review Task；通知 DJI SE |
| `APPROVED` | 触发知识入库 Pipeline；发送通知；生成 PDF 报告 |
| `REJECTED` | 发送拒绝通知（含反馈）；Agent 可重提 |

### 4.4 Human vs AI Decision Model

```
AI 评审角色: 顾问 (Advisory)
    - 输出结构化评分和建议
    - 不直接触发 APPROVED/REJECTED
    - 置信度 < 0.6 时，自动标记为"需重点人工复核"

Platform Reviewer 角色: 过滤器 (Filter)
    - 可接受 AI 结论（快速通道）
    - 可覆写 AI 评分（需填写理由）
    - 可驳回案例回草稿（不经 DJI）

DJI SE 角色: 终裁 (Ground Truth)
    - 最终 APPROVED/REJECTED 决定
    - 所有 DJI 决定自动录入知识库
    - DJI 覆写 AI 的情况生成 Disagreement 记录
```

---

## 5. RAG Service Design（核心）

### 5.1 RAG Pipeline

```
输入: CasePage (page_id, content_text, metadata)
         │
    ┌────▼────────────────────────────────────────────┐
    │  Query Builder                                   │
    │  - 提取页面关键维度（技术选型、行业、部署规模）   │
    │  - 构造多角度检索 Query (3-5 个 Query 变体)      │
    └────┬────────────────────────────────────────────┘
         │
    ┌────▼────────────────────────────────────────────┐
    │  Retrieval Engine (pgvector)                     │
    │  - Rubric 知识检索 (top-k=5)                    │
    │  - 历史案例检索 (top-k=5, 同 industry)          │
    │  - 历史评审意见检索 (top-k=3)                   │
    │  - 分歧案例检索 (top-k=2, 强制纳入)             │
    └────┬────────────────────────────────────────────┘
         │
    ┌────▼────────────────────────────────────────────┐
    │  Ranking & Fusion                                │
    │  - RRF (Reciprocal Rank Fusion) 合并多路结果    │
    │  - 元数据权重加成 (同行业 +0.2, 同region +0.1)  │
    │  - 去重 & 截断至 top-12 上下文片段              │
    └────┬────────────────────────────────────────────┘
         │
    ┌────▼────────────────────────────────────────────┐
    │  LLM Evaluation (GPT-4o)                         │
    │  - System Prompt: 严格评审者角色                 │
    │  - 注入: Rubric + 检索上下文 + 当前页面内容     │
    │  - 强制 JSON 输出 (response_format)             │
    └────┬────────────────────────────────────────────┘
         │
    ┌────▼────────────────────────────────────────────┐
    │  Result Structuring & Validation                 │
    │  - Pydantic 解析 LLM 输出                       │
    │  - 置信度计算（基于检索相关性 + 模型温度）       │
    │  - 写入 Review 表 + 更新 Case 状态              │
    └─────────────────────────────────────────────────┘
```

### 5.2 Knowledge Sources

| 知识库 | 描述 | 更新频率 |
|---|---|---|
| **Rubric Knowledge** | DJI 官方评审标准，按维度分章节 | 版本发布时（手动，Admin） |
| **Case Knowledge** | 所有 APPROVED 案例的页级内容 | 每次案例审批后自动入库 |
| **Review Knowledge** | 人工评审意见和评分记录 | 每次 DJI/Platform 评审后 |
| **Disagreement Knowledge** | AI 与人工显著分歧的案例 | 自动捕获，优先级最高 |

### 5.3 Label Governance System

```
Ground Truth 优先级:
DJI SE 判断 > Platform Reviewer 判断 > 人工标注 > AI 输出

标签冲突解决逻辑:
1. 若 DJI 与 AI 分数差 > 20 分 → 记录为 Major Disagreement
2. 若 Platform 覆写 AI → 记录为 Minor Disagreement
3. Disagreement 记录自动加权进入检索（下次相似案例必检索）
4. Admin 可手动标记特定 Review 为"标准参考" → 提升其检索权重
```

### 5.4 Disagreement Engine

```python
class DisagreementRecord(Base):
    __tablename__ = "disagreement_records"

    id: UUID
    case_id: UUID
    case_page_id: Optional[UUID]
    ai_review_id: UUID
    human_review_id: UUID
    disagreement_type: str          # score_gap / decision_flip / issue_miss
    ai_score: float
    human_score: float
    score_gap: float                # abs(ai - human)
    severity: str                   # minor(<10) / major(10-25) / critical(>25)
    dimension: str                  # 哪个评审维度分歧
    ai_reasoning: str
    human_reasoning: str
    is_training_signal: bool        # 是否已用于 RAG 权重更新
    resolved_at: Optional[datetime]
    created_at: datetime

# 训练信号生成逻辑
def generate_training_signal(record: DisagreementRecord):
    if record.severity in ["major", "critical"]:
        # 1. 将 human 评审文本入库，元数据标注 is_correction=True
        # 2. 降低 AI 对应 Rubric 片段的检索权重
        # 3. 通知 Admin 审核此分歧
        embed_and_store(
            content=record.human_reasoning,
            metadata={
                "source": "disagreement_correction",
                "case_id": record.case_id,
                "dimension": record.dimension,
                "is_correction": True,
                "weight_boost": 1.5,
            }
        )
```

---

## 6. Vector Database Design（pgvector）

### 6.1 Collections（pgvector 表设计）

```sql
-- Rubric 知识向量表
CREATE TABLE rubric_vectors (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content     TEXT NOT NULL,
    embedding   vector(1536),           -- text-embedding-3-small
    rubric_id   UUID REFERENCES rubrics(id),
    dimension   TEXT,                   -- 评审维度名称
    version     TEXT,                   -- rubric 版本
    industry    TEXT[],                 -- 适用行业
    region      TEXT[],
    weight      FLOAT DEFAULT 1.0,      -- 检索权重（可由Admin调整）
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 案例页面向量表
CREATE TABLE case_vectors (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content           TEXT NOT NULL,
    embedding         vector(1536),
    case_page_id      UUID REFERENCES case_pages(id),
    case_id           UUID REFERENCES cases(id),
    page_type         TEXT,
    industry          TEXT,
    region            TEXT,
    overall_score     FLOAT,            -- 该案例最终得分（APPROVED后填入）
    label_source      TEXT,             -- dji / platform / ai
    status            TEXT,             -- approved / rejected
    rubric_version    TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- 评审意见向量表
CREATE TABLE review_vectors (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content       TEXT NOT NULL,        -- 评审意见文本
    embedding     vector(1536),
    review_id     UUID REFERENCES reviews(id),
    review_type   TEXT,                 -- ai / platform / dji
    dimension     TEXT,
    decision      TEXT,                 -- approve / reject / revise
    score         FLOAT,
    industry      TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 分歧记录向量表
CREATE TABLE disagreement_vectors (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content              TEXT NOT NULL,  -- 人工纠正的评审文本
    embedding            vector(1536),
    disagreement_id      UUID REFERENCES disagreement_records(id),
    dimension            TEXT,
    severity             TEXT,
    is_correction        BOOL DEFAULT TRUE,
    weight_boost         FLOAT DEFAULT 1.5,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- 所有向量表均建立 IVFFlat 索引
CREATE INDEX ON rubric_vectors       USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX ON case_vectors         USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX ON review_vectors       USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX ON disagreement_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### 6.2 Embedding Strategy

| 策略 | 适用场景 | Chunk 大小 |
|---|---|---|
| **Page-level embedding** | 整页内容的语义检索 | ~800 tokens |
| **Structured embedding** | 仅嵌入结构化字段（标题+摘要+评分） | ~200 tokens |
| **Issue-based embedding** | 单条评审问题描述的精准匹配 | ~100 tokens |

```python
def embed_case_page(page: CasePage) -> List[EmbeddingRecord]:
    records = []

    # 1. Full page embedding
    records.append(embed(
        content=page.content_text,
        strategy="page_level",
        metadata={...}
    ))

    # 2. Structured summary embedding（标题+类型+关键词）
    summary = f"[{page.page_type}] {page.title}\n{extract_keywords(page.content_text)}"
    records.append(embed(content=summary, strategy="structured", metadata={...}))

    return records
```

### 6.3 Metadata Schema

所有向量记录均携带元数据用于过滤：

```python
{
    "industry": "retail",          # 行业标签
    "region": "APAC",              # 地区
    "rubric_version": "v2.1",      # Rubric版本（确保评审一致性）
    "review_source": "dji",        # 标签来源优先级
    "score": 85.5,                 # 关联评分
    "status": "approved",          # 案例状态
    "page_type": "architecture",   # 页面类型
    "is_correction": False,        # 是否为纠正记录
    "weight_boost": 1.0,           # 检索权重调整因子
    "created_at": "2026-05-17"     # 时间用于新鲜度加权
}
```

### 6.4 Retrieval Strategy

```python
def hybrid_retrieve(
    query_embedding: List[float],
    query_text: str,
    metadata_filter: dict,
    top_k: int = 10
) -> List[RetrievedChunk]:

    # 1. 向量相似度检索（余弦相似度）
    vector_results = db.execute("""
        SELECT *, 1 - (embedding <=> :query_vec) AS similarity
        FROM case_vectors
        WHERE industry = :industry
          AND status = 'approved'
          AND rubric_version = :rubric_version
        ORDER BY embedding <=> :query_vec
        LIMIT :top_k
    """, {**metadata_filter, "query_vec": query_embedding, "top_k": top_k * 2})

    # 2. 全文检索（BM25 via pg_trgm）
    text_results = db.execute("""
        SELECT *, ts_rank(to_tsvector(content), plainto_tsquery(:query)) AS bm25_score
        FROM case_vectors
        WHERE to_tsvector(content) @@ plainto_tsquery(:query)
        ORDER BY bm25_score DESC
        LIMIT :top_k
    """, {"query": query_text, "top_k": top_k * 2})

    # 3. RRF 融合
    merged = reciprocal_rank_fusion(vector_results, text_results)

    # 4. 元数据权重加成
    for chunk in merged:
        if chunk.metadata.get("is_correction"):
            chunk.score *= chunk.metadata.get("weight_boost", 1.5)
        if chunk.metadata.get("review_source") == "dji":
            chunk.score *= 1.2

    return sorted(merged, key=lambda x: x.score, reverse=True)[:top_k]
```

---

## 7. Prompt Engineering System

### 7.1 System Prompt

```python
SYSTEM_PROMPT = """
You are a strict and objective case evaluation expert for DJI security solution integrations.

ROLE CONSTRAINTS:
- You evaluate based ONLY on the provided rubric criteria and retrieved context.
- You do NOT hallucinate scores, facts, or references not present in the input.
- You do NOT approve or reject cases — you provide advisory scores and findings only.
- Your output MUST conform exactly to the JSON schema provided.
- If evidence is insufficient to score a dimension, output score: null and explain why.

SCORING PHILOSOPHY:
- Be conservative. Partial evidence = partial score.
- Technical claims without data support should be penalized.
- Comparison to approved reference cases should inform your calibration.

OUTPUT LANGUAGE: Match the language of the case content (zh-CN or en-US).
"""
```

### 7.2 Evaluation Prompt Logic

```python
EVALUATION_PROMPT_TEMPLATE = """
# Current Evaluation Target
**Page Type**: {page_type}
**Industry**: {industry} | **Region**: {region}
**Rubric Version**: {rubric_version}

# Rubric Criteria (Retrieved)
{rubric_context}

# Reference Cases (Approved, similar industry)
{reference_cases_context}

# Historical Review Notes (for calibration)
{review_notes_context}

# Disagreement Cases (Critical - pay extra attention)
{disagreement_context}

# Case Content to Evaluate
{case_page_content}

# Your Task
Evaluate the above case page against each rubric dimension.
For each dimension:
1. Cite specific evidence from the case content
2. Compare against reference cases where relevant
3. Assign a score from 0-100
4. List concrete issues found
5. Provide actionable recommendations

Respond in the exact JSON schema below.
"""
```

### 7.3 Output Schema

```python
class DimensionScore(BaseModel):
    dimension: str
    score: Optional[float] = Field(None, ge=0, le=100)
    evidence: str
    issues: List[str]
    recommendations: List[str]

class AIReviewOutput(BaseModel):
    page_id: str
    overall_score: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    dimension_scores: List[DimensionScore]
    critical_issues: List[dict]        # [{severity, page_ref, description}]
    rewrite_suggestions: List[dict]    # [{section, original_text, suggestion}]
    reference_cases_used: List[str]    # 引用的参考案例ID
    reasoning_summary: str             # 评审推理摘要（供人工阅读）
    evaluation_metadata: dict          # {model, prompt_version, retrieval_count, latency_ms}
```

### 7.4 Prompt Versioning System

```python
class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: UUID
    prompt_type: str                   # system / evaluation / summary
    version: str                       # "v1.0", "v1.1"
    content: str                       # 完整 prompt 文本
    is_active: bool
    is_canary: bool                    # A/B 测试用
    canary_percentage: float           # 0-100, 流量比例
    performance_metrics: dict          # JSONB {avg_score, disagreement_rate, latency}
    created_by: UUID
    activated_at: Optional[datetime]
    deprecated_at: Optional[datetime]
    created_at: datetime

# Canary 路由逻辑
def get_active_prompt(prompt_type: str) -> PromptVersion:
    canary = get_canary_prompt(prompt_type)
    if canary and random.random() < canary.canary_percentage / 100:
        return canary
    return get_stable_prompt(prompt_type)
```

---

## 8. Notification System

### 8.1 Event Types & Triggers

| 事件 | 接收人 | 触发时机 |
|---|---|---|
| `CaseSubmitted` | Platform Reviewer | 案例进入 AI 评审后 |
| `AIReviewCompleted` | Platform Reviewer | AI 评审完成，任务分配后 |
| `PlatformReviewCompleted` | DJI SE | 平台评审完成 |
| `DJIReviewCompleted` | Agent | DJI 完成评审 |
| `CaseApproved` | Agent + Org Admin | 案例通过，含 PDF 报告 |
| `CaseRejected` | Agent | 案例被拒，含拒绝原因 |
| `SLABreached` | Admin + Reviewer | 评审超时 SLA |
| `DisagreementDetected` | DJI SE + Admin | AI 与人工分歧超阈值 |

### 8.2 Message Builder（AI Summary）

```python
async def build_notification_message(event: CaseEvent, recipient: User) -> NotificationMessage:
    case = get_case(event.case_id)
    review = get_latest_review(event.case_id)

    # AI 生成执行摘要（仅 APPROVED/REJECTED 时）
    if event.type in ["CaseApproved", "CaseRejected"]:
        executive_summary = await llm.generate(
            prompt=SUMMARY_PROMPT.format(
                case_title=case.title,
                review_findings=review.issues,
                decision=review.decision,
                recipient_role=recipient.role,
            ),
            max_tokens=300,
        )
    else:
        executive_summary = None

    return NotificationMessage(
        recipient=recipient,
        subject=build_subject(event, case),
        executive_summary=executive_summary,
        key_issues=extract_top_issues(review, n=3),
        recommendations=extract_top_recommendations(review, n=3),
        portal_link=build_portal_link(case.id, recipient.role),
        permissions=get_visible_fields(recipient.role),  # RBAC 过滤
    )
```

### 8.3 Delivery Channels

```python
class NotificationService:
    async def send(self, message: NotificationMessage):
        tasks = []

        # 邮件（所有用户）
        tasks.append(self.email_sender.send(
            to=message.recipient.email,
            subject=message.subject,
            body=render_template("email/case_event.html", message),
        ))

        # 站内通知
        tasks.append(self.portal_notifier.push(
            user_id=message.recipient.id,
            payload=message.to_portal_payload(),
        ))

        # PDF 报告（仅 APPROVED，发给 Agent 和 DJI SE）
        if message.include_pdf:
            pdf_bytes = await self.pdf_generator.generate(
                template="report/case_approved.html",
                context=message.to_report_context(),
            )
            tasks.append(self.email_sender.send_with_attachment(
                to=message.recipient.email,
                attachment=pdf_bytes,
                filename=f"case_report_{message.case_id}.pdf",
            ))

        await asyncio.gather(*tasks, return_exceptions=True)
```

### 8.4 Permission Filtering

```python
ROLE_VISIBLE_FIELDS = {
    RoleEnum.AGENT: [
        "overall_score", "key_issues", "recommendations",
        "decision", "portal_link",
        # 不包含: ai_raw_output, disagreement_data, reviewer_identity
    ],
    RoleEnum.PLATFORM_REVIEWER: [
        "overall_score", "dimension_scores", "ai_raw_output",
        "key_issues", "recommendations", "decision",
    ],
    RoleEnum.DJI_SE: ["*"],   # 全部字段
    RoleEnum.ADMIN: ["*"],
}
```

---

## 9. Ops & Observability Platform（核心运维系统）

### 9.1 RAG Knowledge Manager

```
功能:
├── Rubric 编辑器 (富文本 + 版本对比)
│   ├── 新建 / 编辑 Rubric 章节
│   ├── 版本发布（触发全量重新 Embed）
│   └── 版本回滚
├── 知识库状态面板
│   ├── 各集合向量数量
│   ├── 最近入库记录
│   └── 入库失败告警
└── 知识权重管理
    ├── 按 source / industry 调整检索权重
    └── 手动标记"标准参考"案例
```

### 9.2 Vector DB Explorer

```
功能:
├── 相似度检索测试
│   ├── 输入文本 → 查看 top-k 检索结果
│   ├── 元数据过滤器
│   └── 相似度分数可视化
├── Embedding 检视
│   ├── 查看指定 case_page 的 embedding 向量信息
│   └── UMAP 降维可视化（集群分布）
└── 数据质量检查
    ├── 重复向量检测
    └── 低质量 Chunk 标记
```

### 9.3 Evaluation Trace Viewer

```
功能:
└── 对任意 AI Review，展示完整推理链路:
    ├── Step 1: Query Builder 生成的查询列表
    ├── Step 2: 各知识库检索结果（含相似度分数）
    ├── Step 3: RRF 融合后的 top-k 上下文
    ├── Step 4: 注入 LLM 的完整 Prompt（脱敏）
    ├── Step 5: LLM 原始响应
    └── Step 6: Pydantic 解析结果 + 置信度计算
```

### 9.4 System Logs & Audit Trail

```python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: UUID
    timestamp: datetime
    actor_id: UUID
    actor_role: str
    action: str               # case.submit / review.override / rubric.update / ...
    resource_type: str        # case / review / user / rubric / prompt
    resource_id: UUID
    old_value: Optional[dict] # JSONB
    new_value: Optional[dict] # JSONB
    ip_address: str
    user_agent: str
    request_id: str           # 关联请求追踪
    result: str               # success / failure
    error_message: Optional[str]
```

**审计场景:**
- 所有状态变更
- 所有评审覆写操作
- Rubric 知识库编辑
- Prompt 版本发布/回滚
- 用户权限变更

### 9.5 Prompt Version Manager

```
功能:
├── Prompt 列表（type / version / active 状态）
├── Prompt 编辑器（支持变量高亮）
├── 性能对比
│   ├── 各版本平均置信度
│   ├── 各版本 Disagreement 率
│   └── 各版本平均延迟
├── A/B 测试配置（设置 canary 百分比）
└── 一键回滚
```

### 9.6 Disagreement Analyzer

```
功能:
├── 分歧热力图（按 dimension × industry 矩阵）
├── 分歧趋势图（时间序列，Major/Critical 分级）
├── 高频分歧 Dimension TOP 10
├── 系统偏差检测
│   ├── AI 系统性高估 / 低估某行业
│   └── AI 对特定 region 的评分偏差
├── 单条分歧详情（AI vs 人工对比视图）
└── 批量标记为训练信号
```

### 9.7 Model Performance Dashboard

| 指标 | 说明 | 告警阈值 |
|---|---|---|
| AI 评审通过率 | AI recommend approve 中最终 APPROVED 的比例 | < 60% 告警 |
| Major Disagreement 率 | score gap > 20 的比例 | > 15% 告警 |
| 平均评审延迟 | AI 评审耗时（秒） | > 60s 告警 |
| 置信度分布 | 各置信度区间的案例分布 | < 0.5 超过 30% 告警 |
| Rubric 覆盖率 | 每次评审平均检索到的 Rubric 维度数 | < 80% 告警 |
| 知识库增长 | 每周新增向量数 | 停滞 > 2周 告警 |

---

## 10. Database Design（ERD 级）

```sql
-- ============================================================
-- Identity & Access
-- ============================================================
CREATE TABLE orgs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    region      TEXT,
    tier        TEXT CHECK (tier IN ('gold','silver','bronze')),
    is_active   BOOL DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE departments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID REFERENCES orgs(id),
    name            TEXT NOT NULL,
    is_dji_internal BOOL DEFAULT FALSE
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name       TEXT,
    org_id          UUID REFERENCES orgs(id),
    department_id   UUID REFERENCES departments(id),
    role            TEXT CHECK (role IN ('agent','platform_reviewer','dji_se','admin')),
    is_active       BOOL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Case Domain
-- ============================================================
CREATE TABLE cases (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID REFERENCES orgs(id),
    created_by          UUID REFERENCES users(id),
    title               TEXT NOT NULL,
    industry            TEXT,
    region              TEXT,
    status              TEXT DEFAULT 'DRAFT',
    current_version_id  UUID,
    rubric_version      TEXT DEFAULT 'v1.0',
    tags                JSONB DEFAULT '[]',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    submitted_at        TIMESTAMPTZ,
    closed_at           TIMESTAMPTZ
);

CREATE TABLE case_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID REFERENCES cases(id),
    version_number  INT NOT NULL,
    submitted_by    UUID REFERENCES users(id),
    change_summary  TEXT,
    is_current      BOOL DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE case_pages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_version_id     UUID REFERENCES case_versions(id),
    page_number         INT NOT NULL,
    page_type           TEXT,
    title               TEXT,
    content_text        TEXT,
    content_html        TEXT,
    word_count          INT DEFAULT 0,
    has_images          BOOL DEFAULT FALSE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE attachments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID REFERENCES cases(id),
    case_version_id UUID REFERENCES case_versions(id),
    file_name       TEXT NOT NULL,
    file_type       TEXT,
    s3_key          TEXT NOT NULL,
    file_size_bytes INT,
    uploaded_by     UUID REFERENCES users(id),
    is_primary      BOOL DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Review Domain
-- ============================================================
CREATE TABLE review_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID REFERENCES cases(id),
    review_type     TEXT CHECK (review_type IN ('ai','platform','dji')),
    assigned_to     UUID REFERENCES users(id),
    status          TEXT DEFAULT 'pending',
    priority        INT DEFAULT 3,
    due_at          TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    sla_breached    BOOL DEFAULT FALSE
);

CREATE TABLE reviews (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID REFERENCES cases(id),
    case_version_id     UUID REFERENCES case_versions(id),
    review_task_id      UUID REFERENCES review_tasks(id),
    reviewer_id         UUID REFERENCES users(id),
    review_type         TEXT,
    overall_score       FLOAT,
    dimension_scores    JSONB DEFAULT '{}',
    issues              JSONB DEFAULT '[]',
    recommendations     JSONB DEFAULT '[]',
    decision            TEXT,
    confidence          FLOAT,
    is_override         BOOL DEFAULT FALSE,
    override_reason     TEXT,
    raw_llm_output      JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Rubric & Prompt Versioning
-- ============================================================
CREATE TABLE rubrics (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        TEXT NOT NULL,
    version      TEXT NOT NULL,
    content      TEXT,
    dimensions   JSONB DEFAULT '[]',
    is_active    BOOL DEFAULT FALSE,
    created_by   UUID REFERENCES users(id),
    activated_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE prompt_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_type         TEXT,
    version             TEXT NOT NULL,
    content             TEXT NOT NULL,
    is_active           BOOL DEFAULT FALSE,
    is_canary           BOOL DEFAULT FALSE,
    canary_percentage   FLOAT DEFAULT 0,
    performance_metrics JSONB DEFAULT '{}',
    created_by          UUID REFERENCES users(id),
    activated_at        TIMESTAMPTZ,
    deprecated_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Disagreement & Audit
-- ============================================================
CREATE TABLE disagreement_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID REFERENCES cases(id),
    case_page_id        UUID REFERENCES case_pages(id),
    ai_review_id        UUID REFERENCES reviews(id),
    human_review_id     UUID REFERENCES reviews(id),
    disagreement_type   TEXT,
    ai_score            FLOAT,
    human_score         FLOAT,
    score_gap           FLOAT,
    severity            TEXT CHECK (severity IN ('minor','major','critical')),
    dimension           TEXT,
    ai_reasoning        TEXT,
    human_reasoning     TEXT,
    is_training_signal  BOOL DEFAULT FALSE,
    resolved_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    actor_id        UUID,
    actor_role      TEXT,
    action          TEXT NOT NULL,
    resource_type   TEXT,
    resource_id     UUID,
    old_value       JSONB,
    new_value       JSONB,
    ip_address      TEXT,
    user_agent      TEXT,
    request_id      TEXT,
    result          TEXT DEFAULT 'success',
    error_message   TEXT
);

-- ============================================================
-- Indexes
-- ============================================================
CREATE INDEX idx_cases_org_status       ON cases(org_id, status);
CREATE INDEX idx_cases_status           ON cases(status);
CREATE INDEX idx_case_pages_version     ON case_pages(case_version_id);
CREATE INDEX idx_reviews_case           ON reviews(case_id, review_type);
CREATE INDEX idx_disagreements_severity ON disagreement_records(severity, created_at);
CREATE INDEX idx_audit_actor            ON audit_logs(actor_id, timestamp);
CREATE INDEX idx_audit_resource         ON audit_logs(resource_type, resource_id);
```

---

## 11. API Design（FastAPI）

### Case APIs

```
# 案例 CRUD
POST   /api/v1/cases                                          # 创建草稿案例
GET    /api/v1/cases                                          # 列表（含分页/过滤）
GET    /api/v1/cases/{case_id}                                # 案例详情
PATCH  /api/v1/cases/{case_id}                                # 更新草稿
POST   /api/v1/cases/{case_id}/submit                         # 提交案例
POST   /api/v1/cases/{case_id}/withdraw                       # 撤回（5分钟内）
DELETE /api/v1/cases/{case_id}                                # 删除草稿

# 版本管理
GET    /api/v1/cases/{case_id}/versions                       # 版本历史
GET    /api/v1/cases/{case_id}/versions/{version_id}          # 指定版本

# 页面管理
POST   /api/v1/cases/{case_id}/pages                          # 添加页面
PUT    /api/v1/cases/{case_id}/pages/{page_id}                # 更新页面
DELETE /api/v1/cases/{case_id}/pages/{page_id}                # 删除页面

# 附件
POST   /api/v1/cases/{case_id}/attachments                    # 上传（返回 S3 presigned PUT URL）
GET    /api/v1/cases/{case_id}/attachments/{id}/download      # 获取临时下载URL
DELETE /api/v1/cases/{case_id}/attachments/{id}               # 删除附件
```

### Review APIs

```
# AI 评审
GET    /api/v1/cases/{case_id}/reviews/ai                     # 获取AI评审结果
POST   /api/v1/cases/{case_id}/reviews/ai/trigger             # 手动触发重新评审（Admin）

# 平台评审
GET    /api/v1/reviews/tasks                                   # 我的评审任务列表
GET    /api/v1/reviews/tasks/{task_id}                         # 任务详情
POST   /api/v1/cases/{case_id}/reviews/platform               # 提交平台评审
PATCH  /api/v1/cases/{case_id}/reviews/platform/{review_id}   # 修改平台评审

# DJI评审
POST   /api/v1/cases/{case_id}/reviews/dji                    # 提交DJI终审
GET    /api/v1/cases/{case_id}/reviews                        # 案例全部评审历史

# 覆写
POST   /api/v1/reviews/{review_id}/override                   # 覆写评审（含理由）
```

### RAG APIs

```
# 知识检索（Ops用）
POST   /api/v1/rag/search                                      # 知识库相似检索测试
GET    /api/v1/rag/trace/{review_id}                           # 获取AI评审推理链路

# 知识管理
POST   /api/v1/rag/rubrics                                     # 创建Rubric版本
PUT    /api/v1/rag/rubrics/{rubric_id}/activate                # 激活Rubric版本
POST   /api/v1/rag/rubrics/{rubric_id}/reindex                 # 触发重新Embedding

# 分歧管理
GET    /api/v1/rag/disagreements                               # 分歧列表（含过滤）
GET    /api/v1/rag/disagreements/{id}                          # 分歧详情
POST   /api/v1/rag/disagreements/{id}/mark-training-signal     # 标记为训练信号
```

### Ops APIs

```
# Dashboard
GET    /api/v1/ops/dashboard                                   # 系统总览指标
GET    /api/v1/ops/performance                                  # 模型性能指标（时间范围）

# Prompt 管理
GET    /api/v1/ops/prompts                                     # Prompt版本列表
POST   /api/v1/ops/prompts                                     # 创建新版本
PUT    /api/v1/ops/prompts/{id}/activate                       # 激活
PUT    /api/v1/ops/prompts/{id}/canary                         # 设置为Canary
POST   /api/v1/ops/prompts/{id}/rollback                       # 回滚

# 审计日志
GET    /api/v1/ops/audit-logs                                  # 审计日志（含过滤）

# 向量 DB 探索
POST   /api/v1/ops/vectors/search                              # 向量检索调试
GET    /api/v1/ops/vectors/stats                               # 各集合统计
```

### Notification APIs

```
POST   /api/v1/notifications/test                              # 测试发送通知（Admin）
GET    /api/v1/notifications/my                                # 我的通知列表
PUT    /api/v1/notifications/{id}/read                         # 标记已读
GET    /api/v1/notifications/settings                          # 通知设置
PUT    /api/v1/notifications/settings                          # 更新通知偏好
```

**通用响应格式:**

```python
class APIResponse(BaseModel):
    success: bool
    data: Optional[Any]
    error: Optional[str]
    request_id: str          # 用于追踪
    timestamp: datetime

class PaginatedResponse(APIResponse):
    data: List[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
```

---

## 12. System Workflow（End-to-End）

```
┌──────────────────────────────────────────────────────────────────────┐
│                        完整业务流水线                                  │
└──────────────────────────────────────────────────────────────────────┘

① Agent 创建案例
   └─ POST /cases → 创建 Case(DRAFT) + CaseVersion(v1)

② Agent 上传附件 & 填写页面内容
   └─ POST /attachments → S3 presigned upload
   └─ POST /pages → 填充 CasePage 内容

③ Agent 提交案例
   └─ POST /cases/{id}/submit
   └─ Case 状态: DRAFT → SUBMITTED
   └─ 异步触发: AI Review Task 入队

④ AI 评审（异步后台任务）
   ├─ 遍历所有 CasePage
   ├─ 每页执行 RAG Pipeline（见 5.1）
   ├─ 汇总页级评分 → 计算 overall_score
   ├─ 写入 Review 表（reviewer_id=NULL）
   └─ Case 状态: SUBMITTED → AI_REVIEWED
   └─ 触发: Platform Reviewer 任务分配 + 邮件通知

⑤ Platform Reviewer 复核
   ├─ 查看 AI 评审结果
   ├─ 确认 / 覆写 AI 结论（记录 is_override=True）
   ├─ 可驳回回草稿（含反馈）
   └─ Case 状态: AI_REVIEWED → PLATFORM_REVIEWED
   └─ 触发: DJI SE 任务分配 + 邮件通知

⑥ DJI SE 终审
   ├─ 查看完整评审链路（含 AI 原始输出）
   ├─ 提交最终决定（APPROVED / REJECTED）
   └─ Case 状态: → APPROVED 或 REJECTED

⑦-A 通过分支（APPROVED）
   ├─ 触发知识入库 Pipeline
   │   ├─ 所有 CasePage Embedding → case_vectors
   │   ├─ DJI Review 意见 Embedding → review_vectors
   │   └─ 若存在 Disagreement → disagreement_vectors
   ├─ 生成 PDF 审批报告
   └─ 发送通知（Agent + Org Admin）

⑦-B 拒绝分支（REJECTED）
   ├─ 记录拒绝原因（入 review_vectors 作为负样本）
   ├─ 生成拒绝通知（含详细反馈）
   └─ Agent 可基于反馈修改后重新提交（创建新 Version）

⑧ 持续学习闭环
   ├─ Disagreement Engine 分析 AI vs DJI 分歧
   ├─ 高严重性分歧入库 disagreement_vectors（权重加成）
   ├─ Ops Dashboard 呈现偏差趋势
   └─ Admin 基于分析调整 Rubric / Prompt → RAG 质量提升
```

---

## 13. Deployment Architecture

### 13.1 Docker Setup

```yaml
# docker-compose.yml
version: "3.9"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/dsec
      - REDIS_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - S3_ENDPOINT_URL=http://minio:9000
      - S3_ACCESS_KEY=minioadmin
      - S3_SECRET_KEY=minioadmin
      - S3_BUCKET=dsec-attachments
      - JWT_SECRET=${JWT_SECRET}
      - SMTP_HOST=${SMTP_HOST}
      - SMTP_USER=${SMTP_USER}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./app:/app/app   # hot reload in dev
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: dsec
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - miniodata:/data

volumes:
  pgdata:
  miniodata:
```

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev gcc weasyprint \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN alembic upgrade head

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### 13.2 Railway Deployment

```toml
# railway.toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 3

[environments.production]
PORT = "8000"
PYTHON_ENV = "production"
```

**Railway 服务配置:**

| 资源 | 配置 |
|---|---|
| Web Service | FastAPI，1 instance，512MB RAM，CPU auto-scale |
| Postgres Addon | Railway Postgres 16，内置 pgvector 扩展 |
| 环境变量 | Railway Dashboard 管理，不入代码库 |
| CI/CD | 连接 GitHub main 分支，push 自动构建部署 |

---

## 14. Security Model

### 认证机制

```python
# JWT Bearer Token
# Access Token: 30分钟有效
# Refresh Token: 7天有效，存储于 HttpOnly Cookie

class TokenPayload(BaseModel):
    sub: str         # user_id
    org_id: str
    role: str
    exp: int
    jti: str         # JWT ID，用于撤销

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = verify_jwt(token)
    user = await get_user(payload.sub)
    if not user.is_active:
        raise HTTPException(401, "User deactivated")
    return user
```

### RBAC 执行

```python
def require_role(*roles: RoleEnum):
    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return current_user
    return dependency

@router.post("/cases/{case_id}/reviews/dji")
async def submit_dji_review(
    case_id: UUID,
    current_user: User = Depends(require_role(RoleEnum.DJI_SE, RoleEnum.ADMIN))
):
    ...
```

### 数据隔离

```python
class OrgIsolationMiddleware:
    async def __call__(self, request: Request, call_next):
        if request.user and request.user.role == RoleEnum.AGENT:
            request.state.org_filter = request.user.org_id
        else:
            request.state.org_filter = None  # DJI SE / Admin 不限制
        return await call_next(request)
```

### 安全措施汇总

| 措施 | 实现方式 |
|---|---|
| Prompt Injection 防护 | System Prompt 禁止指令覆写；LLM 输出经 Pydantic 严格解析 |
| S3 权限控制 | 服务端签名 URL，15分钟过期，客户端不持有长效凭证 |
| SQL 注入防护 | SQLAlchemy ORM + 参数化查询，无原生 SQL 拼接 |
| 速率限制 | Redis sliding window（API: 100 req/min；AI触发: 10 req/hour/org）|
| 敏感数据脱敏 | Audit Log 中对密码、Token 字段自动 mask |
| HTTPS 强制 | Railway 自动 TLS |

---

## 15. System Principles

```
原则 1: AI Cannot Decide Workflow
  AI 评审输出仅为"建议"（advisory），不触发任何状态变更
  所有状态变更必须由人类操作触发

原则 2: Human is Final Authority
  Platform Reviewer 可驳回 AI 结论并附原因
  驳回记录必须存储，供 Disagreement Engine 分析

原则 3: DJI is Ground Truth
  DJI SE 的所有评审结论无条件入库
  DJI 的决定不可被任何其他角色覆写
  DJI 与 AI 的分歧自动记录为训练信号

原则 4: RAG Must Be Self-Improving
  每次 APPROVED 案例必须自动入向量库
  每次 DJI 覆写 AI 必须触发 Disagreement 记录
  Admin 可调整权重，但系统应能自动优化

原则 5: Metadata > Embeddings
  检索时优先用元数据过滤（industry、region、rubric_version）
  语义相似性仅在同元数据分组内排序
  元数据质量直接决定 RAG 质量

原则 6: Auditability is Non-Negotiable
  所有 AI 决策必须可追溯（Evaluation Trace）
  所有人工操作必须有审计日志
  系统不允许存在无日志的状态变更
```

---

## 16. MVP Cut Plan

**目标**: 3个月内上线可用版本，验证核心评审流程。

### 保留功能（MVP）

```
✓ 用户认证 (JWT)
✓ 基础 RBAC (4个角色)
✓ 案例创建/提交/版本管理
✓ 文件上传（S3）
✓ AI 评审（RAG + GPT-4o）
✓ 页级 Embedding（pgvector）
✓ Platform 评审
✓ DJI 终审
✓ 基础知识入库（APPROVED 后）
✓ 邮件通知（关键事件）
✓ 基础 Ops 面板（Disagreement 列表 + 性能指标）
✓ 审计日志
```

### 裁减功能（Post-MVP）

```
✗ Kafka / 消息队列   → 替换: AsyncIO BackgroundTasks
✗ 微服务拆分         → 替换: 单 FastAPI 应用 + 模块化组织
✗ Redis 任务队列     → 替换: 数据库状态轮询
✗ UMAP 可视化        → 延后至 v1.2
✗ A/B Prompt 测试    → 延后至 v1.1（先单版本）
✗ PDF 报告           → 延后至 v1.1
✗ WebSocket 实时通知 → 延后（先轮询）
✗ 细粒度权重调整 UI  → 延后
```

### MVP 技术栈

| 层级 | 选型 |
|---|---|
| Backend | FastAPI + SQLAlchemy (async) + Alembic |
| Database | PostgreSQL 16 + pgvector |
| AI | OpenAI (text-embedding-3-small + GPT-4o) |
| Storage | AWS S3 / Cloudflare R2 |
| Notify | SMTP (Gmail / SendGrid) |
| Deploy | Railway（单服务） |
| Dev | Docker Compose |

---

## 17. Future Extensions

### Phase 2（6-12个月）

```
多 Agent 评审系统
  └─ 不同维度由专业 Agent 并行评审
     （架构Agent / 商业价值Agent / 合规Agent）
  └─ Agent Orchestrator 汇总并仲裁

PDF 报告生成
  └─ WeasyPrint 渲染 HTML 模板
  └─ 自动插入AI评审图表和评分可视化

实时通知
  └─ WebSocket 推送评审进度
  └─ 浏览器 Notification API
```

### Phase 3（12-24个月）

```
Fine-tuned 评审模型
  └─ 基于积累的 Disagreement 数据微调专用模型
  └─ 替代通用 GPT-4o，降低成本 + 提升领域准确率

Active Learning Loop
  └─ 系统主动识别"不确定"案例，优先推送给 DJI SE
  └─ 低置信度案例自动进入强化标注队列

Advanced Governance Layer
  └─ 多租户 SaaS（支持非 DJI 组织独立使用）
  └─ Rubric 市场（不同行业定制化评审标准）
  └─ API 开放平台（第三方系统集成）
```

---

*文档版本: v1.0 | 生成日期: 2026-05-17*
