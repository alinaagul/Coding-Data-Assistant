import { useRef, useState } from 'react'
import { Send, Sparkles, Clock, Rows3, Copy } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { PageHeader, Spinner } from '../components/Layout'
import { api } from '../api/client'
import { useToast } from '../context/ToastContext'
import { ChatMessage } from '../types'

const EXAMPLES = [
  'Which tables are the largest?',
  'Recommend indexes.',
  'Explain this schema.',
  'Find duplicate records.',
  'Find orphan records.',
  'Analyze database performance.',
]

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(true)
  const [busy, setBusy] = useState(false)
  const { push } = useToast()
  const bottomRef = useRef<HTMLDivElement>(null)

  async function send(text?: string) {
    const message = (text ?? input).trim()
    if (!message || busy) return
    setInput('')
    const history = messages.map((m) => ({ role: m.role, content: m.content }))
    setMessages((m) => [...m, { role: 'user', content: message }])
    setBusy(true)
    try {
      const resp: any = await api.chat(message, history, thinking)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: resp.answer,
          generatedSql: resp.generated_sql,
          execution: resp.execution,
          elapsedS: resp.elapsed_s,
        },
      ])
    } catch (e: any) {
      push('error', e.message || 'AI chat failed.')
    } finally {
      setBusy(false)
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <PageHeader
        title="AI Chat"
        subtitle="Ask qwen3:8b about your schema, performance, or data quality."
        action={
          <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <input type="checkbox" checked={thinking} onChange={(e) => setThinking(e.target.checked)} />
            Show reasoning trace
          </label>
        }
      />

      <div className="flex-1 overflow-y-auto card p-4 mb-3 space-y-4">
        {messages.length === 0 && (
          <div className="h-full grid place-items-center">
            <div className="max-w-md text-center">
              <Sparkles className="mx-auto mb-3 text-query" size={26} />
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">Try asking:</p>
              <div className="flex flex-wrap gap-2 justify-center">
                {EXAMPLES.map((e) => (
                  <button
                    key={e}
                    onClick={() => send(e)}
                    className="text-xs px-3 py-1.5 rounded-full bg-slate-100 dark:bg-white/5 hover:bg-query/10 hover:text-query focus-ring"
                  >
                    {e}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                m.role === 'user' ? 'bg-query text-canvas' : 'bg-slate-100 dark:bg-white/5'
              }`}
            >
              <div className="prose prose-sm dark:prose-invert max-w-none prose-pre:bg-canvas prose-pre:text-slate-100">
                <ReactMarkdown>{m.content}</ReactMarkdown>
              </div>

              {m.execution && (
                <div className="mt-3 border-t border-border-light dark:border-border pt-2">
                  <div className="flex items-center gap-3 text-[11px] text-slate-500 dark:text-slate-400 mb-2">
                    <span className="flex items-center gap-1"><Clock size={11} /> {m.elapsedS?.toFixed(1)}s</span>
                    <span className="flex items-center gap-1"><Rows3 size={11} /> {m.execution.row_count} rows</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(m.generatedSql || '')}
                      className="flex items-center gap-1 hover:text-query"
                    >
                      <Copy size={11} /> Copy SQL
                    </button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs font-mono">
                      <thead>
                        <tr className="text-left text-slate-500 dark:text-slate-400">
                          {m.execution.columns.map((c) => <th key={c} className="py-1 pr-3">{c}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {m.execution.rows.slice(0, 10).map((row, ri) => (
                          <tr key={ri} className="border-t border-border-light dark:border-border/50">
                            {m.execution!.columns.map((c) => <td key={c} className="py-1 pr-3">{String(row[c])}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex justify-start">
            <div className="rounded-2xl px-4 py-3 bg-slate-100 dark:bg-white/5">
              <Spinner size={14} />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send()
        }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your database..."
          className="flex-1 px-4 py-3 rounded-xl bg-surface-light dark:bg-surface border border-border-light dark:border-border focus-ring text-sm"
        />
        <button
          type="submit"
          disabled={busy}
          className="px-4 rounded-xl bg-query text-canvas font-medium disabled:opacity-50 focus-ring"
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  )
}
