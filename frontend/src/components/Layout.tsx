import { ReactNode } from 'react'
import Sidebar from './Sidebar'

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-canvas-light dark:bg-canvas">
      <Sidebar />
      <main className="flex-1 min-w-0 p-6 md:p-8 max-w-[1400px] mx-auto w-full">{children}</main>
    </div>
  )
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
      <div>
        <h1 className="font-display font-bold text-2xl">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <div
      className="animate-spin rounded-full border-2 border-slate-300 dark:border-slate-600 border-t-query"
      style={{ width: size, height: size }}
    />
  )
}

export function Badge({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'good' | 'bad' | 'warn' }) {
  const tones: Record<string, string> = {
    default: 'bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-300',
    good: 'bg-emerald-500/10 text-emerald-500',
    bad: 'bg-danger/10 text-danger',
    warn: 'bg-index/10 text-index',
  }
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${tones[tone]}`}>{children}</span>
}
