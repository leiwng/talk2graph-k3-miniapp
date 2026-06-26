// 与后端 DSL 对齐（仅前端需要的字段）

export interface GeoObject {
  id: string
  kind: 'point' | 'segment' | 'line' | 'polygon' | 'circle'
  a?: string
  b?: string
  vertices?: string[]
  hint?: [number, number] | null
  definition?: {
    type: 'center_radius' | 'center_through' | 'incircle' | 'circumcircle'
    center?: string
    through?: string
    of?: string
    radius?: number
  }
}

export interface Constraint {
  type: string
  // 不强类型化 — 直接展示原 JSON
  [key: string]: any
}

export interface Annotation {
  target: string
  kind: 'length' | 'angle' | 'radius' | 'label'
  show?: boolean
  text?: string | null
}

export interface DSL {
  version: string
  objects: GeoObject[]
  constraints: Constraint[]
  annotations: Annotation[]
  labels: Record<string, string>
  style?: Record<string, any>
}

export interface Solution {
  coordinates: Record<string, [number, number]>
  circles: Record<string, { center: [number, number]; radius: number }>
  residual: number
  method: string
}

export interface SessionInfo {
  id: string
  title: string | null
  llm_provider: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  dsl_patch: string | null
  llm_provider: string | null
  tokens_in: number | null
  tokens_out: number | null
  latency_ms: number | null
  error_kind: 'refuse' | 'solve' | 'patch' | 'network' | null
  created_at: string
  // 前端临时字段（乐观更新）
  pending?: boolean
}

export interface ChatResult {
  ok: boolean
  seq?: number
  dsl?: DSL
  solution?: Solution
  svg?: string
  provider?: string
  attempts?: number
  error?: string
  error_kind?: 'refuse' | 'solve' | 'patch' | 'network' | null
  raw_reason?: string
}

export interface ProviderInfo {
  name: string
  model: string
  enabled: boolean
  is_default: boolean
}

export interface PatchOp {
  op: 'add' | 'remove' | 'replace'
  path: string
  value?: any
}
