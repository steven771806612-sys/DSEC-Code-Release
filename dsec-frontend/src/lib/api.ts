// src/lib/api.ts — Axios instance + typed helpers
import axios, { AxiosError } from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Attach token from localStorage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// Generic response wrapper
export interface ApiResponse<T = unknown> {
  success: boolean
  data: T
  error?: string
  request_id?: string
}

export async function get<T>(url: string, params?: object): Promise<T> {
  const res = await api.get<ApiResponse<T>>(url, { params })
  return res.data.data
}

export async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await api.post<ApiResponse<T>>(url, body)
  return res.data.data
}

export async function patch<T>(url: string, body?: unknown): Promise<T> {
  const res = await api.patch<ApiResponse<T>>(url, body)
  return res.data.data
}

export async function put<T>(url: string, body?: unknown): Promise<T> {
  const res = await api.put<ApiResponse<T>>(url, body)
  return res.data.data
}

export async function del<T>(url: string): Promise<T> {
  const res = await api.delete<ApiResponse<T>>(url)
  return res.data.data
}
