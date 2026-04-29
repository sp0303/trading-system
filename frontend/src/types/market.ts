export interface Strategy {
  name: string;
  status: string;
  confidence: number;
  note: string;
}

export interface Breadth {
  advancers: number;
  decliners: number;
}

export interface Instrument {
  symbol: string;
  label: string;
  lastPrice: number;
  last_price?: number; // Backend compatibility
  change: number;
  change_pct?: number;
  sector?: string;
  sentiment?: string;
  volume?: string;
  breadth?: Breadth | string;
  strategies?: Strategy[];
  intraday_change_pct?: number;
}

export interface Signal {
  id: number;
  symbol: string;
  timestamp: string;
  direction: 'BUY' | 'SELL' | 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  entry: number;
  entry_price?: number;
  target_l1: number;
  target_l2: number;
  target_l3: number;
  target_1?: number;
  target_2?: number;
  target_3?: number;
  stop_loss: number;
  probability: number;
  confidence: number;
  strategy: string;
  regime: string;
  mae_expected?: number;
  mfe_expected?: number;
  trade_type: string;
}

export interface HistoryPoint {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface HistoryData {
  symbol: string;
  series: HistoryPoint[];
}

export interface Benchmark extends Instrument {
  series: HistoryPoint[];
}

export interface PaperOrder {
  id: number;
  client_order_id: string;
  trade_signal_id?: number;
  symbol: string;
  side: 'BUY' | 'SELL' | 'SHORT';
  qty: number;
  requested_price?: number;
  avg_fill_price?: number;
  status: string;
  note?: string;
  strategy_name?: string;
  regime?: string;
  created_at: string;
  updated_at?: string;
}

export interface PaperFill {
  id: number;
  client_order_id: string;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  fees: number;
  timestamp: string;
}

export interface PaperPosition {
  symbol: string;
  net_qty: number;
  avg_price: number;
  last_price?: number;
  realized_pnl: number;
  unrealized_pnl: number;
  updated_at?: string;
}

export interface PaperPnlSummary {
  realized_pnl: number;
  unrealized_pnl: number;
  open_positions: number;
  closed_trades: number;
}

export interface PaperAccount {
  starting_capital: number;
  available_cash: number;
  invested_capital: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_equity: number;
  updated_at: string;
}
