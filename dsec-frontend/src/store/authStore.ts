// src/store/authStore.ts — Zustand auth state
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface UserInfo {
  id: string
  email: string
  full_name?: string
  role: 'agent' | 'platform_reviewer' | 'dji_se' | 'admin'
  org_id: string
}

interface AuthState {
  user: UserInfo | null
  accessToken: string | null
  setAuth: (user: UserInfo, token: string) => void
  logout: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      setAuth: (user, accessToken) => {
        localStorage.setItem('access_token', accessToken)
        set({ user, accessToken })
      },
      logout: () => {
        localStorage.removeItem('access_token')
        set({ user: null, accessToken: null })
      },
      isAuthenticated: () => !!get().accessToken && !!get().user,
    }),
    { name: 'dsec-auth', partialize: (s) => ({ user: s.user, accessToken: s.accessToken }) }
  )
)
