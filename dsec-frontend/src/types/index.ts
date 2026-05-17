// src/types/index.ts — shared TypeScript types
export interface Case {
  id: string
  org_id: string
  created_by: string
  title: string
  industry?: string
  region?: string
  status: CaseStatus
  rubric_version: string
  tags: string[]
  created_at: string
  updated_at: string
  submitted_at?: string
  closed_at?: string
  current_version_id?: string
}

export type CaseStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'AI_REVIEWED'
  | 'PLATFORM_REVIEWED'
  | 'DJI_REVIEWED'
  | 'APPROVED'
  | 'REJECTED'

export interface CasePage {
  id: string
  case_id: string
  case_version_id: string
  page_number: number
  page_type?: string
  title?: string
  content_text?: string
  word_count: number
  has_images: boolean
  created_at: string
}

export interface ReviewIssueObject {
  severity?: string
  description: string
}

export type ReviewIssue = string | ReviewIssueObject

export interface Review {
  id: string
  case_id: string
  review_type: 'ai' | 'platform' | 'dji'
  reviewer_id?: string
  overall_score?: number
  dimension_scores: Record<string, unknown>
  issues: ReviewIssue[]
  recommendations: string[]
  decision?: string
  confidence?: number
  is_override: boolean
  override_reason?: string
  created_at: string
  updated_at: string
}

export interface ReviewTask {
  id: string
  case_id: string
  review_type: string
  assigned_to?: string
  status: string
  priority: number
  due_at?: string
  sla_breached: boolean
  created_at: string
}

export interface DisagreementRecord {
  id: string
  case_id: string
  disagreement_type?: string
  ai_score?: number
  human_score?: number
  score_gap?: number
  severity?: string
  dimension?: string
  is_training_signal: boolean
  created_at: string
}

export interface PromptVersion {
  id: string
  prompt_type: string
  version: string
  content: string
  is_active: boolean
  is_canary: boolean
  canary_percentage: number
  performance_metrics: Record<string, unknown>
  created_at: string
  activated_at?: string
}

export interface DashboardMetrics {
  total_cases: number
  cases_by_status: Record<string, number>
  ai_approval_rate: number
  major_disagreement_rate: number
  avg_review_latency_seconds: number
  total_vectors: Record<string, number>
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  has_next: boolean
}
