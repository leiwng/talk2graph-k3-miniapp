// 与后端 DSL 对齐（仅前端需要的字段）

export interface GeoObject {
  id: string
  kind: 'point' | 'segment' | 'line' | 'polygon' | 'circle' | 'axis' | 'transformed_point' | 'transformed_polygon' | 'curve' | 'arc' | 'sector' | 'region' | 'number_line' | 'aux_line' | 'bow' | 'annular_sector' | 'cube' | 'cuboid' | 'cylinder' | 'cone' | 'sphere' | 'bar_chart' | 'line_chart' | 'pie_chart'
  a?: string
  b?: string
  vertices?: string[]
  hint?: [number, number] | null
  // axis 字段
  origin?: string
  x_range?: [number, number]
  y_range?: [number, number]
  tick_step?: number
  show_grid?: boolean
  show_ticks?: boolean
  x_label?: string
  y_label?: string
  grid_size?: number | null
  // W11 派生对象字段
  source?: string
  transform?: {
    type: 'rotation' | 'translation' | 'reflection' | 'central_symmetry' | 'homothety'
    center?: string
    angle?: number
    dx?: number
    dy?: number
    line?: string
    ratio?: number
  }
  vertex_suffix?: string
  // V2-B curve 字段（V2-G.4 加 pieces）
  expr?: string
  var?: 'x' | 'y'
  domain?: [number, number]
  samples?: number
  color?: string
  dash?: string
  pieces?: { expr: string; domain: [number, number] }[] | null
  // V2-G.1 arc / sector 字段
  center?: string
  from_point?: string
  to_point?: string
  radius?: number | null
  ccw?: boolean
  // P3 V3.4 annular_sector 字段
  r_inner?: number
  // V2-G.3 region / number_line / aux_line 字段
  boundary?: string[]
  fill_color?: string
  fill_opacity?: number
  stroke?: string | null
  range?: [number, number]
  show_numbers?: boolean
  label?: string
  extended?: boolean
  // V3.1 立体几何字段
  vertex?: string
  edge?: number
  length?: number
  width?: number
  height?: number
  center_bottom?: string
  // V3.2 统计图表字段
  data?: number[]
  labels?: string[]
  bar_color?: string
  line_color?: string
  colors?: string[] | null
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
  // P0：会话抽屉展示用
  message_count?: number
  last_user_nl?: string | null
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
  fallback?: boolean | null
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
  fallback?: boolean
  fallback_reason?: string | null
  solve_repaired?: boolean
  solve_repair_reason?: string | null
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

// ===================== V2-F.1: 用户管理 =====================

export interface User {
  id: string
  email: string
  username: string
  role: 'user' | 'admin'
  status: 'active' | 'disabled' | 'pending_email_verification'
  last_login_at: string | null
  created_at: string
  // P1 V2-F.3
  email_verified?: boolean
  wechat_nickname?: string | null
}

export interface AuthResp {
  token: string
  user: User
}

export interface AuditLogItem {
  id: number
  actor_id: string | null
  actor_email: string | null
  action: string
  target_type: string | null
  target_id: string | null
  metadata: Record<string, any> | null
  ip_address: string | null
  user_agent: string | null
  created_at: string
}

export interface AuditLogListResp {
  items: AuditLogItem[]
  total: number
  limit: number
  offset: number
}

// ===================== V2-F.2: 付费 + 配额 =====================

export interface Plan {
  code: string
  name: string
  description: string | null
  feature_bullets: string[]
  price_cents: number
  currency: string
  period: string
  daily_graph_limit: number
  sort_order: number
}

export interface Entitlement {
  plan_code: string
  plan_name: string
  status: 'free' | 'active' | 'expired'
  daily_limit: number  // 0 = 无限
  used_today: number
  remaining: number  // -1 = 无限
}

export interface Subscription {
  plan: Plan
  entitlement: Entitlement
  current_period_start: string | null
  current_period_end: string | null
}

export interface Order {
  id: string
  plan_code: string
  amount_cents: number
  currency: string
  status: 'pending' | 'paid' | 'expired' | 'closed' | 'refunded' | 'failed'
  provider: string
  provider_out_trade_no: string
  created_at: string
  paid_at: string | null
  expires_at: string | null
  closed_at: string | null
}

export interface CreateOrderResp {
  order: Order
  pay_url: string
}

// ===================== P2 V3.3：Admin 管理 =====================

export interface AdminUser {
  id: string
  email: string
  username: string
  role: 'user' | 'admin'
  status: 'active' | 'disabled' | 'pending_email_verification'
  email_verified: boolean
  wechat_nickname: string | null
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface AdminUserListResp {
  items: AdminUser[]
  total: number
  limit: number
  offset: number
}

export interface AdminUserDetail {
  user: AdminUser
  sessions_count: number
  snapshots_count: number
  subscription: {
    plan_code: string
    status: string
    daily_graph_limit_override: number | null
    current_period_start: string | null
    current_period_end: string | null
  } | null
}

export interface AdminPlan {
  code: string
  name: string
  description: string | null
  price_cents: number
  period: string
  daily_graph_limit: number
  status: string
  sort_order: number
}

export interface AdminStats {
  since: string
  days: number
  sessions: number
  messages: number
  snapshots: number
  users: number
  verified_users: number
  providers: Array<{
    provider: string
    calls: number
    tokens_in: number
    tokens_out: number
    avg_latency_ms: number
  }>
}
