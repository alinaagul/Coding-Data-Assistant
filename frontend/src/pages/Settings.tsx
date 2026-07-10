import { useEffect, useState } from 'react'
import { PlugZap, CheckCircle2, XCircle, Cpu } from 'lucide-react'
import { PageHeader, Spinner, Badge } from '../components/Layout'
import { api } from '../api/client'
import { useToast } from '../context/ToastContext'
import { ConnectionPayload } from '../types'

const EMPTY: ConnectionPayload = {
  server: '',
  port: 1433,
  database: '',
  username: '',
  password: '',
  encrypt: true,
  trust_server_certificate: true,
}

export default function Settings() {
  const [form, setForm] = useState<ConnectionPayload>(EMPTY)
  const [testing, setTesting] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [testResult, setTestResult] = useState<any>(null)
  const [status, setStatus] = useState<any>(null)
  const { push } = useToast()

  useEffect(() => {
    api.status().then(setStatus).catch(() => {})
  }, [])

  function update<K extends keyof ConnectionPayload>(key: K, value: ConnectionPayload[K]) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function test() {
    setTesting(true)
    setTestResult(null)
    try {
      const res: any = await api.testConnection(form)
      setTestResult(res)
      push(res.success ? 'success' : 'error', res.success ? 'Connection succeeded.' : res.error)
    } catch (e: any) {
      push('error', e.message || 'Test failed.')
    } finally {
      setTesting(false)
    }
  }

  async function saveAndConnect() {
    setConnecting(true)
    try {
      await api.connect(form)
      push('success', 'Connected and saved as the active database.')
      const s = await api.status()
      setStatus(s)
    } catch (e: any) {
      push('error', e.message || 'Could not connect.')
    } finally {
      setConnecting(false)
    }
  }

  return (
    <div>
      <PageHeader title="Settings" subtitle="Configure your SQL Server connection and check the local AI model." />

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 card p-5">
          <h3 className="font-display font-semibold mb-4 flex items-center gap-2">
            <PlugZap size={17} className="text-query" /> SQL Server Connection
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-4 leading-relaxed">
            Use a <strong>read-only</strong> SQL Server login. The backend independently blocks any
            INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/EXEC/MERGE statement regardless of this
            login's permissions, but a read-only login is required as defense in depth.
          </p>

          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="Server Name">
              <input value={form.server} onChange={(e) => update('server', e.target.value)} className="input" placeholder="sql.mycompany.com" />
            </Field>
            <Field label="Port">
              <input type="number" value={form.port} onChange={(e) => update('port', Number(e.target.value))} className="input" />
            </Field>
            <Field label="Database Name">
              <input value={form.database} onChange={(e) => update('database', e.target.value)} className="input" placeholder="AdventureWorks" />
            </Field>
            <Field label="Username">
              <input value={form.username} onChange={(e) => update('username', e.target.value)} className="input" placeholder="readonly_user" />
            </Field>
            <Field label="Password">
              <input type="password" value={form.password} onChange={(e) => update('password', e.target.value)} className="input" />
            </Field>
            <Field label="Encryption">
              <label className="flex items-center gap-2 text-sm mt-2">
                <input type="checkbox" checked={form.encrypt} onChange={(e) => update('encrypt', e.target.checked)} />
                Encrypt connection
              </label>
            </Field>
          </div>

          <div className="flex gap-2 mt-5">
            <button onClick={test} disabled={testing} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-slate-100 dark:bg-white/5 text-sm disabled:opacity-50 focus-ring">
              {testing ? <Spinner size={14} /> : <PlugZap size={14} />} Test Connection
            </button>
            <button onClick={saveAndConnect} disabled={connecting} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-query text-canvas text-sm font-medium disabled:opacity-50 focus-ring">
              {connecting ? <Spinner size={14} /> : <CheckCircle2 size={14} />} Save & Connect
            </button>
          </div>

          {testResult && (
            <div className={`mt-4 p-3 rounded-lg text-sm flex items-start gap-2 ${testResult.success ? 'bg-emerald-500/10' : 'bg-danger/10'}`}>
              {testResult.success ? <CheckCircle2 size={16} className="text-emerald-500 mt-0.5" /> : <XCircle size={16} className="text-danger mt-0.5" />}
              <div>
                {testResult.success ? (
                  <>
                    <p>Connected in {testResult.elapsed_s}s.</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{testResult.server_version}</p>
                    {testResult.warnings?.map((w: string, i: number) => (
                      <p key={i} className="text-xs text-index mt-1">⚠ {w}</p>
                    ))}
                  </>
                ) : (
                  <p>{testResult.error}</p>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="card p-5 h-fit">
          <h3 className="font-display font-semibold mb-4 flex items-center gap-2">
            <Cpu size={17} className="text-index" /> AI Model
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400">Model</span>
              <span className="font-mono">{status?.ai_model?.model ?? 'qwen3:8b'}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400">Ollama server</span>
              {status?.ai_model?.ollama_running ? <Badge tone="good">Running</Badge> : <Badge tone="bad">Unreachable</Badge>}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400">Model pulled</span>
              {status?.ai_model?.model_pulled ? <Badge tone="good">Yes</Badge> : <Badge tone="warn">No</Badge>}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400">Database</span>
              {status?.connected ? <Badge tone="good">Connected</Badge> : <Badge tone="bad">Not connected</Badge>}
            </div>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-4">
            This app only supports qwen3:8b, run locally via Ollama. No other model or cloud API is used.
          </p>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
      {children}
    </label>
  )
}
