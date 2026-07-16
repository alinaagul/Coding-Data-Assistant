import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Explorer from './pages/Explorer'
import Chat from './pages/Chat'
import SqlConsole from './pages/SqlConsole'
import Reports from './pages/Reports'
import Settings from './pages/Settings'
import { ThemeProvider } from './context/ThemeContext'
import { ToastProvider } from './context/ToastContext'

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <BrowserRouter>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/explorer" element={<Explorer />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/console" element={<SqlConsole />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Layout>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  )
}
