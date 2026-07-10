import { LucideIcon } from 'lucide-react'

export default function StatCard({
  label,
  value,
  icon: Icon,
  accent = 'query',
}: {
  label: string
  value: string | number
  icon: LucideIcon
  accent?: 'query' | 'index' | 'danger'
}) {
  const accentClasses: Record<string, string> = {
    query: 'text-query bg-query/10',
    index: 'text-index bg-index/10',
    danger: 'text-danger bg-danger/10',
  }
  return (
    <div className="card p-4 flex items-center gap-4">
      <div className={`w-10 h-10 rounded-lg grid place-items-center ${accentClasses[accent]}`}>
        <Icon size={19} />
      </div>
      <div>
        <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
        <p className="font-display font-bold text-xl leading-tight">{value}</p>
      </div>
    </div>
  )
}
