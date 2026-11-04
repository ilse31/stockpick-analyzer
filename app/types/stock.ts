export type Horizon = '1' | '5'

export interface Stock {
  symbol: string
  name: string
}

interface TradePlan {
  entry_limit: number
  entry_time: string
  stop: number
  risk: number
  deadline: string
  sample: number
  hits: number
  stops: number
  timed_exits: number
  tp_window: { session: number; start: string } | null
}

export interface Candidate {
  symbol: string
  name: string
  close: number
  probability: number
  change: number
  tp: number
  target: number
  tp_hit: number
  tp_n: number
  accuracy: number
  test_n: number
  plan: TradePlan
}

interface ScreenerResult {
  date: string
  ranks: Record<Horizon, Candidate[]>
}

interface StockEvidence {
  symbol: string
  close: number
  up: number
  change: number
  accuracy: number
  test_n: number
  brier_edge: number
  qualified: boolean
}

export interface ScanResult extends ScreenerResult {
  listed: number
  selected: number
  quoted: number
  counts: { analyzed: number; skipped: number; failed: number }
  universe: Record<Horizon, StockEvidence[]>
}

export interface StockResult extends ScreenerResult {
  stock: Stock & { close: number | null }
  status: 'analyzed' | 'skipped'
}

export interface AiContext {
  date: string
  horizon: Horizon
  stock?: StockResult['stock']
  candidates: Omit<Candidate, 'name' | 'target'>[]
}

export interface AiUniverse {
  date: string
  horizon: Horizon
  stocks: StockEvidence[]
}
