import { useState } from 'react'
import { FileText, Download, Loader2 } from 'lucide-react'
import { PageHeader, Spinner } from '../components/Layout'
import { api } from '../api/client'
import { useToast } from '../context/ToastContext'

const REPORTS = [
  { id: 'health', label: 'Database Health Report', fetch: () => api.healthReport() },
  { id: 'performance', label: 'Performance Report', fetch: () => api.performanceReport() },
  { id: 'missing-indexes', label: 'Missing Index Report', fetch: () => api.missingIndexes() },
  { id: 'data-quality', label: 'Data Quality Report', fetch: () => api.dataQuality() },
]

function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function Reports() {
  const [activeId, setActiveId] = useState<string | null>(null)
  const [data, setData] = useState<any>(null)
  const [narrative, setNarrative] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const { push } = useToast()

  async function run(id: string, fetcher: () => Promise<any>) {
    setBusy(id)
    setActiveId(id)
    setNarrative(null)
    try {
      const res = await fetcher()
      setData(res)
      if (['health', 'performance', 'data-quality'].includes(id)) {
        try {
          const summary: any = await api.aiSummary(id)
          setNarrative(summary.narrative)
        } catch { /* narrative is best-effort */ }
      }
    } catch (e: any) {
      push('error', e.message || 'Failed to generate report.')
    } finally {
      setBusy(null)
    }
  }

  function exportJson() {
    if (!data) return
    download(`${activeId}_report.json`, JSON.stringify(data, null, 2), 'application/json')
  }

  function exportCsv() {
    if (!data) return
    const rows = Array.isArray(data) ? data : [data]
    if (rows.length === 0) return push('info', 'No rows to export.')
    const cols = Object.keys(rows[0])
    const csv = [cols.join(','), ...rows.map((r) => cols.map((c) => JSON.stringify(r[c] ?? '')).join(','))].join('\n')
    download(`${activeId}_report.csv`, csv, 'text/csv')
  }

  function exportPdfPrint() {
    // Lightweight PDF export via the browser's print dialog (Save as PDF) -
    // avoids pulling in a heavy client-side PDF library for a report view.
    window.print()
  }

  return (
    <div>
      <PageHeader title="Reports" subtitle="Generate and export analysis reports." />

      <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3 mb-6">
        {REPORTS.map((r) => (
          <button
            key={r.id}
            onClick={() => run(r.id, r.fetch)}
            className="card p-4 text-left hover:border-query/50 transition-colors focus-ring"
          >
            <FileText className="text-query mb-2" size={18} />
            <p className="text-sm font-medium">{r.label}</p>
            {busy === r.id && <Loader2 className="animate-spin mt-2 text-slate-400" size={14} />}
          </button>
        ))}
      </div>

      {activeId && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <h3 className="font-display font-semibold">
              {REPORTS.find((r) => r.id === activeId)?.label}
            </h3>
            <div className="flex gap-2">
              <button onClick={exportJson} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 text-xs focus-ring">
                <Download size={12} /> JSON
              </button>
              <button onClick={exportCsv} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 text-xs focus-ring">
                <Download size={12} /> CSV
              </button>
              <button onClick={exportPdfPrint} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 text-xs focus-ring">
                <Download size={12} /> PDF
              </button>
            </div>
          </div>

          {busy === activeId ? (
            <div className="grid place-items-center py-16"><Spinner /></div>
          ) : (
            <>
              {narrative && (
                <div className="mb-4 p-4 rounded-lg bg-query/5 border border-query/20 text-sm whitespace-pre-wrap">
                  {narrative}
                </div>
              )}
              <pre className="text-xs font-mono bg-canvas-light dark:bg-canvas p-4 rounded-lg overflow-x-auto max-h-[420px]">
                {JSON.stringify(data, null, 2)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  )
}
