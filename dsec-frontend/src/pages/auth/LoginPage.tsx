// src/pages/auth/LoginPage.tsx
import axios from 'axios'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { useAuthStore } from '../../store/authStore'
import { post } from '../../lib/api'
import { Spinner } from '../../components/ui/Loading'

interface LoginForm { email: string; password: string }

const roleRedirect: Record<string, string> = {
  agent:             '/agent',
  platform_reviewer: '/reviewer',
  dji_se:            '/dji',
  admin:             '/ops/dashboard',
}

export default function LoginPage() {
  const navigate = useNavigate()
  const { setAuth } = useAuthStore()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>()

  const onSubmit = async (data: LoginForm) => {
    setLoading(true); setError('')
    try {
      const res = await post<{ access_token: string; token_type: string }>('/auth/login', data)
      // Fetch me
      const me = await fetch(`${import.meta.env.VITE_API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${res.access_token}` },
      }).then(r => r.json()).then(d => d.data)
      setAuth(me, res.access_token)
      navigate(roleRedirect[me.role] ?? '/agent')
    } catch (e: unknown) {
      setError(
        axios.isAxiosError<{ detail?: string }>(e)
          ? e.response?.data?.detail ?? '登录失败，请检查邮箱或密码'
          : '登录失败，请检查邮箱或密码'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 to-gray-800 p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="mx-auto w-14 h-14 bg-brand-600 rounded-2xl flex items-center justify-center text-white text-2xl font-bold mb-3">D</div>
          <h1 className="text-white text-2xl font-bold">DSEC AI 评审平台</h1>
          <p className="text-gray-400 text-sm mt-1">DJI 安防案例智能评审系统</p>
        </div>

        <div className="card p-6 shadow-2xl">
          <h2 className="text-lg font-semibold mb-5 text-center">登录账号</h2>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="label">邮箱</label>
              <input
                {...register('email', { required: '请输入邮箱' })}
                type="email"
                placeholder="you@company.com"
                className="input"
              />
              {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email.message}</p>}
            </div>
            <div>
              <label className="label">密码</label>
              <input
                {...register('password', { required: '请输入密码' })}
                type="password"
                placeholder="••••••••"
                className="input"
              />
              {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password.message}</p>}
            </div>
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-3 py-2">
                {error}
              </div>
            )}
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? <Spinner size="sm" /> : '登录'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
