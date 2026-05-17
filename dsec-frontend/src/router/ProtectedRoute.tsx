// src/router/ProtectedRoute.tsx
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { AppShell } from '../components/layout/AppShell'

interface Props {
  children: React.ReactNode
  roles?: string[]
}

export function ProtectedRoute({ children, roles }: Props) {
  const { user, isAuthenticated } = useAuthStore()

  if (!isAuthenticated()) return <Navigate to="/login" replace />
  if (roles && user && !roles.includes(user.role)) return <Navigate to="/unauthorized" replace />

  return <AppShell>{children}</AppShell>
}
