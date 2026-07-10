import { useEffect, useState } from 'react'
import { Table2, Rows3, HardDrive, ListTree, HeartPulse, Clock } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { PageHeader, Spinner } from '../components/Layout'
import StatCard from '../components/StatCard'
import { api } from '../api/client'
import { useToast } from '../context/ToastContext'
import { HealthReport, TableInfo } from '../types'

const PIE_COLORS = ['#3FD6C6', '#F0A954', '#F0615B', '#8B7FE8', '#4C8DF6']

export default function Dashboard() {
  const [health, setHealth] = useState<HealthReport | null>(null)
  const [tables, setTables] = useState<TableInfo[]>([])
  const [perf, setPerf] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [connected, setConnected] = useState(true)
  const { push } = useToast()

  useEffect(() => {
    (async () => {
      try {
        const status: any = await api.status()
        setConnected(status.connected)
        if (!status.connected) {
          setLoading(false)
          return
        }
        const [h, t, p] = await Promise.all([
          api.healthReport(),
          api.listTables(),
          api.performanceReport().catch(() => []),
        ])
        setHealth(h as HealthReport)
        setTables(t as TableInfo[])
        setPerf(p as any[])
      } catch (e: any) {
        push('error', e.message || 'Failed to load dashboard data.')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  if (loading) {
    return (
      <div className="grid place-items-center h-[70vh]">
        <Spinner size={28} />
      </div>
    )
  }

  if (!connected) {
    return (
      <div className="max-w-lg mx-auto mt-24 text-center card p-8">
        <h2 className="font-display font-bold text-lg mb-2">No database connected</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Head to Settings to enter your SQL Server details and connect a read-only login.
        </p>
      </div>
    )
  }

  const largestTables = [...tables].sort((a, b) => b.size_mb - a.size_mb).slice(0, 8)
  const indexPie = [
    { name: 'Indexed tables', value: Math.max(tables.length - (health?.missing_index_count || 0), 0) },
    { name: 'Missing index candidates', value: health?.missing_index_count || 0 },
  ]

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle="Live overview of the connected SQL Server database, analyzed by qwen3:8b."
      />

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
        <StatCard label="Total Tables" value={health?.total_tables ?? '—'} icon={Table2} />
        <StatCard label="Total Rows" value={(health?.total_rows ?? 0).toLocaleString()} icon={Rows3} accent="index" />
        <StatCard label="DB Size (MB)" value={health?.database_size_mb ?? '—'} icon={HardDrive} />
        <StatCard label="Total Indexes" value={health?.total_indexes ?? '—'} icon={ListTree} accent="index" />
        <StatCard
          label="Health Score"
          value={`${health?.health_score ?? '—'} / 100`}
          icon={HeartPulse}
          accent={(health?.health_score ?? 100) < 60 ? 'danger' : 'query'}
        />
        <StatCard
          label="Last Analysis"
          value={health ? new Date(health.generated_at).toLocaleTimeString() : '—'}
          icon={Clock}
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <h3 className="font-display font-semibold mb-3 text-sm">Largest Tables (MB)</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={largestTables} layout="vertical" margin={{ left: 24 }}>
              <XAxis type="number" stroke="#64748b" fontSize={11} />
              <YAxis
                type="category"
                dataKey="table_name"
                width={110}
                stroke="#64748b"
                fontSize={11}
              />
              <Tooltip contentStyle={{ background: '#111A2B', border: '1px solid #20304A', fontSize: 12 }} />
              <Bar dataKey="size_mb" fill="#3FD6C6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4">
          <h3 className="font-display font-semibold mb-3 text-sm">Index Coverage</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={indexPie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={3}>
                {indexPie.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#111A2B', border: '1px solid #20304A', fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4">
          <h3 className="font-display font-semibold mb-3 text-sm">Storage Usage by Table</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={largestTables}>
              <XAxis dataKey="table_name" stroke="#64748b" fontSize={10} interval={0} angle={-25} textAnchor="end" height={60} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={{ background: '#111A2B', border: '1px solid #20304A', fontSize: 12 }} />
              <Bar dataKey="size_mb" fill="#F0A954" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card p-4">
          <h3 className="font-display font-semibold mb-3 text-sm">Query Performance (avg ms)</h3>
          {perf.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-400 py-16 text-center">
              No query stats available yet — run some queries in the SQL Console.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={perf.slice(0, 8)}>
                <XAxis dataKey="query_text" hide />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip contentStyle={{ background: '#111A2B', border: '1px solid #20304A', fontSize: 12 }} />
                <Bar dataKey="avg_elapsed_ms" fill="#8B7FE8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  )
}
