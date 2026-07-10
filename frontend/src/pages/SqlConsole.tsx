import { useState } from 'react'
import { Play, Copy, Download, Wand2, History as HistoryIcon, Trash2 } from 'lucide-react'
import { PageHeader, Spinner, Badge } from '../components/Layout'
import { api } from '../api/client'
import { useToast } from '../context/ToastContext'
import { QueryResult } from '../types'

interface HistoryItem {
  sql: string
  ranAt: string
  rowCount: number
  elapsedS: number
}

export default function SqlConsole() {
  const [sql, setSql] = useState('SELECT TOP 100 * FROM INFORMATION_SCHEMA.TABLES;')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [explanation, setExplanation] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const { push } = useToast()

  async function run() {
    setBusy(true)
    setExplanation(null)
    try {
      const res: any = await api.executeQuery(sql)
      setResult(res)
      setHistory((h) => [
        { sql, ranAt: new Date().toLocaleTimeString(), rowCount: res.row_count, elapsedS: res.elapsed_s },
        ...h,
      ].slice(0, 20))
      push('success', `Query returned ${res.row_count} rows in ${res.elapsed_s}s.`)
    } catch (e: any) {
      push('error', e.message || 'Query failed validation or execution.')
      setResult(null)
    } finally {
      setBusy(false)
    }
  }

  async function explain() {
    setBusy(true)
    try {
      const res: any = await api.explainQuery(sql)
      setExplanation(res.explanation)
    } catch (e: any) {
      push('error', e.message || 'Could not explain query.')
    } finally {
      setBusy(false)
    }
  }

  function downloadCsv() {
    if (!result) return
    const header = result.columns.join(',')
    const rows = result.rows.map((r) => result.columns.map((c) => JSON.stringify(r[c] ?? '')).join(','))
    const csv = [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'query_results.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader title="SQL Console" subtitle="Read-only console. Only SELECT statements are permitted." />

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8 space-y-4">
          <div className="card p-4">
            <textarea
              value={sql}
              onChange={(e) => setSql(e.target.value)}
              spellCheck={false}
              rows={10}
              className="w-full bg-canvas-light dark:bg-canvas font-mono text-sm p-3 rounded-lg border border-border-light dark:border-border focus-ring resize-y"
            />
            <div className="flex flex-wrap gap-2 mt-3">
              <button onClick={run} disabled={busy} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-query text-canvas text-sm font-medium disabled:opacity-50 focus-ring">
                <Play size={14} /> Execute
              </button>
              <button onClick={explain} disabled={busy} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 text-sm focus-ring">
                <Wand2 size={14} /> Explain Query
              </button>
              <button onClick={() => navigator.clipboard.writeText(sql)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 text-sm focus-ring">
                <Copy size={14} /> Copy SQL
              </button>
              <button onClick={downloadCsv} disabled={!result} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 text-sm disabled:opacity-50 focus-ring">
                <Download size={14} /> Download CSV
              </button>
              {busy && <Spinner size={16} />}
            </div>
          </div>

          {explanation && (
            <div className="card p-4 text-sm whitespace-pre-wrap">{explanation}</div>
          )}

          {result && (
            <div className="card p-4">
              <div className="flex items-center gap-3 mb-3 text-xs text-slate-500 dark:text-slate-400">
                <Badge tone="good">{result.row_count} rows</Badge>
                <span>{result.elapsed_s}s</span>
              </div>
              <div className="overflow-x-auto max-h-[420px]">
                <table className="w-full text-xs font-mono">
                  <thead className="sticky top-0 bg-surface-light dark:bg-surface">
                    <tr className="text-left text-slate-500 dark:text-slate-400 border-b border-border-light dark:border-border">
                      {result.columns.map((c) => <th key={c} className="py-2 pr-4">{c}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr key={i} className="border-b border-border-light dark:border-border/50">
                        {result.columns.map((c) => <td key={c} className="py-1.5 pr-4">{String(row[c])}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <div className="col-span-12 lg:col-span-4">
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-display font-semibold text-sm flex items-center gap-1.5">
                <HistoryIcon size={14} /> Query History
              </h3>
              {history.length > 0 && (
                <button onClick={() => setHistory([])} className="text-slate-400 hover:text-danger">
                  <Trash2 size={14} />
                </button>
              )}
            </div>
            <ul className="space-y-2 max-h-[60vh] overflow-y-auto">
              {history.map((h, i) => (
                <li key={i}>
                  <button
                    onClick={() => setSql(h.sql)}
                    className="w-full text-left p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 focus-ring"
                  >
                    <p className="font-mono text-xs truncate">{h.sql}</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      {h.ranAt} · {h.rowCount} rows · {h.elapsedS}s
                    </p>
                  </button>
                </li>
              ))}
              {history.length === 0 && <p className="text-xs text-slate-500 text-center py-6">No queries run yet.</p>}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
