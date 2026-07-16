export interface ConnectionStatus {
  connected: boolean
  connection: Record<string, any> | null
  ai_model: {
    model: string
    ollama_running: boolean
    model_pulled: boolean
  }
}

export interface TableInfo {
  schema_name: string
  table_name: string
  row_count_estimate: number
  size_mb: number
}

export interface ColumnInfo {
  column_name: string
  data_type: string
  max_length: number
  precision: number
  scale: number
  is_nullable: boolean
  is_identity: boolean
  is_primary_key: number
  default_value: string | null
}

export interface IndexInfo {
  index_name: string
  type_desc: string
  is_unique: boolean
  is_primary_key: boolean
  columns: string
  row_count: number
  size_mb: number
}

export interface QueryResult {
  columns: string[]
  rows: Record<string, any>[]
  row_count: number
  elapsed_s: number
  executed_sql: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  generatedSql?: string | null
  execution?: QueryResult | null
  elapsedS?: number
}

export interface HealthReport {
  total_tables: number
  total_rows: number
  total_indexes: number
  database_size_mb: number
  health_score: number
  missing_index_count: number
  null_heavy_column_count: number
  generated_at: string
}

export type ToastKind = 'success' | 'error' | 'info'

export interface ToastMessage {
  id: number
  kind: ToastKind
  text: string
}
