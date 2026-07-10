const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* no-op */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  // connection
  testConnection: (payload: any) => request('/api/connection/test', { method: 'POST', body: JSON.stringify(payload) }),
  connect: (payload: any) => request('/api/connection/connect', { method: 'POST', body: JSON.stringify(payload) }),
  disconnect: () => request('/api/connection/disconnect', { method: 'POST' }),
  status: () => request('/api/connection/status'),

  // schema
  listDatabases: () => request('/api/schema/databases'),
  listTables: () => request('/api/schema/tables'),
  getColumns: (schema: string, table: string) => request(`/api/schema/tables/${schema}/${table}/columns`),
  getIndexes: (schema: string, table: string) => request(`/api/schema/tables/${schema}/${table}/indexes`),
  getConstraints: (schema: string, table: string) => request(`/api/schema/tables/${schema}/${table}/constraints`),
  getForeignKeys: () => request('/api/schema/foreign-keys'),
  getSampleData: (schema: string, table: string, limit = 20) =>
    request(`/api/schema/tables/${schema}/${table}/sample?limit=${limit}`),
  getRowCount: (schema: string, table: string) => request(`/api/schema/tables/${schema}/${table}/row-count`),

  // query
  executeQuery: (sql: string, max_rows = 1000) =>
    request('/api/query/execute', { method: 'POST', body: JSON.stringify({ sql, max_rows }) }),
  validateQuery: (sql: string) => request('/api/query/validate', { method: 'POST', body: JSON.stringify({ sql }) }),
  queryPlan: (sql: string) => request('/api/query/plan', { method: 'POST', body: JSON.stringify({ sql }) }),

  // ai
  chat: (message: string, history: any[], think: boolean) =>
    request('/api/ai/chat', { method: 'POST', body: JSON.stringify({ message, history, think }) }),
  nlToSql: (question: string) => request('/api/ai/nl-to-sql', { method: 'POST', body: JSON.stringify({ question }) }),
  explainQuery: (sql: string) => request('/api/ai/explain-query', { method: 'POST', body: JSON.stringify({ sql }) }),
  optimizeQuery: (sql: string) => request('/api/ai/optimize-query', { method: 'POST', body: JSON.stringify({ sql }) }),

  // reports
  healthReport: () => request('/api/reports/health'),
  performanceReport: () => request('/api/reports/performance'),
  missingIndexes: () => request('/api/reports/missing-indexes'),
  redundantIndexes: () => request('/api/reports/redundant-indexes'),
  nullHeavyColumns: () => request('/api/reports/null-heavy-columns'),
  orphanRecords: () => request('/api/reports/orphan-records'),
  dataQuality: () => request('/api/reports/data-quality'),
  aiSummary: (kind: string) => request(`/api/reports/ai-summary?kind=${kind}`),
}

export { ApiError }
