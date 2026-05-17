// src/lib/utils.ts — shared helpers
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, parseISO } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(iso: string) {
  return format(parseISO(iso), 'yyyy-MM-dd HH:mm')
}

export function statusBadgeClass(status: string) {
  const map: Record<string, string> = {
    DRAFT: 'badge-draft',
    SUBMITTED: 'badge-submitted',
    AI_REVIEWED: 'badge-ai',
    PLATFORM_REVIEWED: 'badge-platform',
    DJI_REVIEWED: 'badge-dji',
    APPROVED: 'badge-approved',
    REJECTED: 'badge-rejected',
  }
  return map[status] ?? 'badge-draft'
}

export function statusLabel(status: string) {
  const map: Record<string, string> = {
    DRAFT: '草稿',
    SUBMITTED: '已提交',
    AI_REVIEWED: 'AI 已评审',
    PLATFORM_REVIEWED: '平台已评审',
    DJI_REVIEWED: 'DJI 已评审',
    APPROVED: '已通过',
    REJECTED: '已拒绝',
  }
  return map[status] ?? status
}

export function roleLabel(role: string) {
  const map: Record<string, string> = {
    agent: '代理商',
    platform_reviewer: '平台评审员',
    dji_se: 'DJI SE',
    admin: '管理员',
  }
  return map[role] ?? role
}
