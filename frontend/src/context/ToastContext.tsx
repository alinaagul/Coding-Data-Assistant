import { createContext, useCallback, useContext, useState, ReactNode } from 'react'
import { ToastKind, ToastMessage } from '../types'
import { CheckCircle2, XCircle, Info, X } from 'lucide-react'

const ToastContext = createContext<{ push: (kind: ToastKind, text: string) => void }>({
  push: () => {},
})

const ICONS: Record<ToastKind, JSX.Element> = {
  success: <CheckCircle2 size={18} className="text-emerald-400" />,
  error: <XCircle size={18} className="text-danger" />,
  info: <Info size={18} className="text-query" />,
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])

  const push = useCallback((kind: ToastKind, text: string) => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, kind, text }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500)
  }, [])

  const dismiss = (id: number) => setToasts((t) => t.filter((x) => x.id !== id))

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="card animate-fade-in flex items-start gap-2 p-3 shadow-lg"
          >
            {ICONS[t.kind]}
            <p className="text-sm flex-1">{t.text}</p>
            <button onClick={() => dismiss(t.id)} className="text-slate-400 hover:text-slate-200">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
