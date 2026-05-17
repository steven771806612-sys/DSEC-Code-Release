// src/components/ui/Loading.tsx
export function Spinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sz = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-10 w-10' }[size]
  return (
    <svg className={`animate-spin ${sz} text-brand-600`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  )
}

export function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Spinner size="lg" />
    </div>
  )
}

export function EmptyState({ title, desc }: { title: string; desc?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-4xl mb-3">📭</div>
      <h3 className="text-gray-700 font-medium">{title}</h3>
      {desc && <p className="text-sm text-gray-500 mt-1">{desc}</p>}
    </div>
  )
}
