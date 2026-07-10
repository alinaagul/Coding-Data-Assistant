import { useEffect, useState } from 'react'
import { Table2, KeyRound, Link2, ListTree, Rows3 } from 'lucide-react'
import { PageHeader, Spinner, Badge } from '../components/Layout'
import { api } from '../api/client'
import { useToast } from '../context/ToastContext'
import { TableInfo, ColumnInfo, IndexInfo } from '../types'
import clsx from 'clsx'

type Tab = 'columns' | 'indexes' | 'constraints' | 'sample'

export default function Explorer() {
  const [tables, setTables] = useState<TableInfo[]>([])
  const [selected, setSelected] = useState<TableInfo | null>(null)
  const [tab, setTab] = useState<Tab>('columns')
  const [columns, setColumns] = useState<ColumnInfo[]>([])
  const [indexes, setIndexes] = useState<IndexInfo[]>([])
  const [constraints, setConstraints] = useState<any[]>([])
  const [sample, setSample] = useState<any[]>([])
  const [rowCount, setRowCount] = useState<number | null>(null)
  const [loadingTables, setLoadingTables] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [filter, setFilter] = useState('')
  const { push } = useToast()

  useEffect(() => {
    (async () => {
      try {
        const t: any = await api.listTables()
        setTables(t)
      } catch (e: any) {
        push('error', e.message || 'Could not load tables. Connect a database in Settings.')
      } finally {
        setLoadingTables(false)
      }
    })()
  }, [])

  async function selectTable(t: TableInfo) {
    setSelected(t)
    setTab('columns')
    setLoadingDetail(true)
    try {
      const [cols, idx, cons, rc] = await Promise.all([
        api.getColumns(t.schema_name, t.table_name),
        api.getIndexes(t.schema_name, t.table_name),
        api.getConstraints(t.schema_name, t.table_name),
        api.getRowCount(t.schema_name, t.table_name),
      ])
      setColumns(cols as ColumnInfo[])
      setIndexes(idx as IndexInfo[])
      setConstraints(cons as any[])
      setRowCount((rc as any).row_count)
    } catch (e: any) {
      push('error', e.message || 'Failed to load table detail.')
    } finally {
      setLoadingDetail(false)
    }
  }

  async function loadSample() {
    if (!selected) return
    setTab('sample')
    if (sample.length > 0) return
    try {
      const rows: any = await api.getSampleData(selected.schema_name, selected.table_name, 20)
      setSample(rows)
    } catch (e: any) {
      push('error', e.message || 'Failed to load sample data.')
    }
  }

  const filteredTables = tables.filter((t) =>
    `${t.schema_name}.${t.table_name}`.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div>
      <PageHeader title="Database Explorer" subtitle="Browse tables, columns, keys, indexes, and sample data." />

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 md:col-span-4 lg:col-span-3 card p-3 h-[75vh] overflow-y-auto">
          <input
            placeholder="Filter tables..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full mb-3 px-3 py-1.5 rounded-lg bg-slate-100 dark:bg-white/5 text-sm focus-ring"
          />
          {loadingTables ? (
            <div className="grid place-items-center py-10"><Spinner /></div>
          ) : (
            <ul className="space-y-0.5">
              {filteredTables.map((t) => (
                <li key={`${t.schema_name}.${t.table_name}`}>
                  <button
                    onClick={() => selectTable(t)}
                    className={clsx(
                      'w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm text-left focus-ring',
                      selected?.table_name === t.table_name
                        ? 'bg-query/10 text-query'
                        : 'hover:bg-slate-100 dark:hover:bg-white/5'
                    )}
                  >
                    <Table2 size={14} className="shrink-0" />
                    <span className="truncate">{t.schema_name}.{t.table_name}</span>
                  </button>
                </li>
              ))}
              {filteredTables.length === 0 && (
                <p className="text-xs text-slate-500 text-center py-6">No tables found.</p>
              )}
            </ul>
          )}
        </div>

        <div className="col-span-12 md:col-span-8 lg:col-span-9 card p-4 min-h-[75vh]">
          {!selected ? (
            <div className="grid place-items-center h-full text-sm text-slate-500 dark:text-slate-400">
              Select a table on the left to inspect it.
            </div>
          ) : (
            <div>
              <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                <div>
                  <h2 className="font-display font-bold text-lg">{selected.schema_name}.{selected.table_name}</h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5">
                    {rowCount?.toLocaleString() ?? '—'} rows · {selected.size_mb} MB
                  </p>
                </div>
                <div className="flex gap-1 bg-slate-100 dark:bg-white/5 p-1 rounded-lg">
                  {[
                    { id: 'columns', label: 'Columns', icon: ListTree },
                    { id: 'indexes', label: 'Indexes', icon: KeyRound },
                    { id: 'constraints', label: 'Constraints', icon: Link2 },
                    { id: 'sample', label: 'Sample Data', icon: Rows3 },
                  ].map(({ id, label, icon: Icon }) => (
                    <button
                      key={id}
                      onClick={() => (id === 'sample' ? loadSample() : setTab(id as Tab))}
                      className={clsx(
                        'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium focus-ring',
                        tab === id ? 'bg-white dark:bg-surface shadow-sm text-query' : 'text-slate-500 dark:text-slate-400'
                      )}
                    >
                      <Icon size={13} /> {label}
                    </button>
                  ))}
                </div>
              </div>

              {loadingDetail ? (
                <div className="grid place-items-center py-16"><Spinner /></div>
              ) : (
                <div className="overflow-x-auto">
                  {tab === 'columns' && (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-border-light dark:border-border">
                          <th className="py-2 pr-4">Column</th>
                          <th className="py-2 pr-4">Type</th>
                          <th className="py-2 pr-4">Nullable</th>
                          <th className="py-2 pr-4">Key</th>
                          <th className="py-2 pr-4">Default</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono">
                        {columns.map((c) => (
                          <tr key={c.column_name} className="border-b border-border-light dark:border-border/50">
                            <td className="py-1.5 pr-4">{c.column_name}</td>
                            <td className="py-1.5 pr-4 text-slate-500 dark:text-slate-400">{c.data_type}</td>
                            <td className="py-1.5 pr-4">{c.is_nullable ? <Badge>NULL</Badge> : <Badge tone="warn">NOT NULL</Badge>}</td>
                            <td className="py-1.5 pr-4">{c.is_primary_key ? <Badge tone="good">PK</Badge> : ''}</td>
                            <td className="py-1.5 pr-4 text-slate-500 dark:text-slate-400">{c.default_value ?? ''}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}

                  {tab === 'indexes' && (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-border-light dark:border-border">
                          <th className="py-2 pr-4">Index</th>
                          <th className="py-2 pr-4">Type</th>
                          <th className="py-2 pr-4">Columns</th>
                          <th className="py-2 pr-4">Unique</th>
                          <th className="py-2 pr-4">Size (MB)</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono">
                        {indexes.map((i) => (
                          <tr key={i.index_name} className="border-b border-border-light dark:border-border/50">
                            <td className="py-1.5 pr-4">{i.index_name}{i.is_primary_key ? ' (PK)' : ''}</td>
                            <td className="py-1.5 pr-4 text-slate-500 dark:text-slate-400">{i.type_desc}</td>
                            <td className="py-1.5 pr-4">{i.columns}</td>
                            <td className="py-1.5 pr-4">{i.is_unique ? 'Yes' : 'No'}</td>
                            <td className="py-1.5 pr-4 text-slate-500 dark:text-slate-400">{i.size_mb ?? '—'}</td>
                          </tr>
                        ))}
                        {indexes.length === 0 && (
                          <tr><td colSpan={5} className="py-6 text-center text-slate-500">No indexes found.</td></tr>
                        )}
                      </tbody>
                    </table>
                  )}

                  {tab === 'constraints' && (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-slate-500 dark:text-slate-400 border-b border-border-light dark:border-border">
                          <th className="py-2 pr-4">Constraint</th>
                          <th className="py-2 pr-4">Type</th>
                          <th className="py-2 pr-4">Column</th>
                        </tr>
                      </thead>
                      <tbody className="font-mono">
                        {constraints.map((c, i) => (
                          <tr key={i} className="border-b border-border-light dark:border-border/50">
                            <td className="py-1.5 pr-4">{c.constraint_name}</td>
                            <td className="py-1.5 pr-4 text-slate-500 dark:text-slate-400">{c.type_desc}</td>
                            <td className="py-1.5 pr-4">{c.column_name}</td>
                          </tr>
                        ))}
                        {constraints.length === 0 && (
                          <tr><td colSpan={3} className="py-6 text-center text-slate-500">No check constraints found.</td></tr>
                        )}
                      </tbody>
                    </table>
                  )}

                  {tab === 'sample' && (
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr className="text-left text-slate-500 dark:text-slate-400 border-b border-border-light dark:border-border">
                          {sample[0] && Object.keys(sample[0]).map((k) => <th key={k} className="py-2 pr-4">{k}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {sample.map((row, i) => (
                          <tr key={i} className="border-b border-border-light dark:border-border/50">
                            {Object.values(row).map((v: any, j) => <td key={j} className="py-1.5 pr-4">{String(v)}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
