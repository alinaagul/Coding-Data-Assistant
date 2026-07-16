import { useEffect, useState } from 'react'
import { Database, Cpu } from 'lucide-react'
import { PageHeader, Badge } from '../components/Layout'
import { api } from '../api/client'

export default function Settings() {
  const [status, setStatus] = useState<any>(null)

  useEffect(() => {
    api.status().then(setStatus).catch(() => {})
  }, [])

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Read-only status. The database connection is configured in backend/.env, not here."
      />

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card p-5">
          <h3 className="font-display font-semibold mb-4 flex items-center gap-2">
            <Database size={17} className="text-query" /> SQL Server Connection
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-4 leading-relaxed">
            Set <code>MSSQL_SERVER</code>, <code>MSSQL_PORT</code>, <code>MSSQL_DATABASE</code>,{' '}
            <code>MSSQL_USERNAME</code>, and <code>MSSQL_PASSWORD</code> in{' '}
            <code>backend/.env</code>, then restart the backend. Use a{' '}
            <strong>read-only</strong> login - the backend independently blocks any
            INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/EXEC/MERGE statement regardless of
            this login's permissions, but a read-only login is required as defense in depth.
          </p>

          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400">Status</span>
              {status?.connected ? <Badge tone="good">Connected</Badge> : <Badge tone="bad">Not connected</Badge>}
            </div>
            {status?.connection && (
              <>
                <Row label="Server" value={`${status.connection.server}:${status.connection.port}`} />
                <Row label="Database" value={status.connection.database} />
                <Row label="Username" value={status.connection.username} />
              </>
            )}
          </div>
        </div>

        <div className="card p-5 h-fit">
          <h3 className="font-display font-semibold mb-4 flex items-center gap-2">
            <Cpu size={17} className="text-index" /> AI Model
          </h3>
          <div className="space-y-2 text-sm">
            <Row label="Model" value={status?.ai_model?.model ?? 'qwen3:8b'} mono />
            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400">Ollama server</span>
              {status?.ai_model?.ollama_running ? <Badge tone="good">Running</Badge> : <Badge tone="bad">Unreachable</Badge>}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500 dark:text-slate-400">Model pulled</span>
              {status?.ai_model?.model_pulled ? <Badge tone="good">Yes</Badge> : <Badge tone="warn">No</Badge>}
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

function Row({ label, value, mono }: { label: string; value?: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-500 dark:text-slate-400">{label}</span>
      <span className={mono ? 'font-mono' : ''}>{value || '-'}</span>
    </div>
  )
}
