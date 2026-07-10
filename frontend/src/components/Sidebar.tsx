import { NavLink } from 'react-router-dom'
import { LayoutGrid, Database, MessageSquare, Terminal, FileBarChart2, Settings2, Moon, Sun, Cpu } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import clsx from 'clsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutGrid },
  { to: '/explorer', label: 'Database Explorer', icon: Database },
  { to: '/chat', label: 'AI Chat', icon: MessageSquare },
  { to: '/console', label: 'SQL Console', icon: Terminal },
  { to: '/reports', label: 'Reports', icon: FileBarChart2 },
  { to: '/settings', label: 'Settings', icon: Settings2 },
]

export default function Sidebar() {
  const { theme, toggle } = useTheme()

  return (
    <aside className="w-64 shrink-0 h-screen sticky top-0 flex flex-col border-r border-border-light dark:border-border bg-surface-light dark:bg-surface">
      <div className="px-5 py-5 flex items-center gap-2 border-b border-border-light dark:border-border">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-query to-index grid place-items-center">
          <Cpu size={18} className="text-canvas" />
        </div>
        <div>
          <p className="font-display font-bold text-sm leading-tight">AI DB Analyst</p>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">qwen3:8b · local</p>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors focus-ring',
                isActive
                  ? 'bg-query/10 text-query'
                  : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5'
              )
            }
          >
            <Icon size={17} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-border-light dark:border-border">
        <button
          onClick={toggle}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5 focus-ring"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
      </div>
    </aside>
  )
}
