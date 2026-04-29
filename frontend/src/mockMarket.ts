const RANGE_POINTS: Record<string, number> = {
  day: 48,
  month: 30,
  year: 52,
};

const RANGE_STEP: Record<string, number> = {
  day: 60 * 30,
  month: 60 * 60 * 24,
  year: 60 * 60 * 24 * 7,
};

interface SymbolConfig {
  label: string;
  basePrice: number;
  drift: number;
  volatility: number;
  sector: string;
  change: number;
  volume: string;
  breadth: string;
  sentiment: string;
}

const SYMBOL_CONFIG: Record<string, SymbolConfig> = {
  NIFTY50: {
    label: "NIFTY 50",
    basePrice: 22480,
    drift: 16,
    volatility: 82,
    sector: "Benchmark",
    change: 0.84,
    volume: "₹18.4L Cr",
    breadth: "34/16",
    sentiment: "Risk-on breadth improving",
  },
  RELIANCE: {
    label: "Reliance Industries",
    basePrice: 2968,
    drift: 4.2,
    volatility: 24,
    sector: "Energy",
    change: 1.36,
    volume: "₹3,240 Cr",
    breadth: "Energy Leadership",
    sentiment: "Institutional accumulation above VWAP",
  },
  TCS: {
    label: "Tata Consultancy Services",
    basePrice: 4028,
    drift: 3.1,
    volatility: 22,
    sector: "Technology",
    change: 0.72,
    volume: "₹1,680 Cr",
    breadth: "IT rotation",
    sentiment: "Trend intact, momentum cooling",
  },
  INFY: {
    label: "Infosys",
    basePrice: 1496,
    drift: 2.4,
    volatility: 16,
    sector: "Technology",
    change: -0.28,
    volume: "₹1,410 Cr",
    breadth: "Mixed internals",
    sentiment: "Range trade unless breakout confirms",
  },
  HDFCBANK: {
    label: "HDFC Bank",
    basePrice: 1674,
    drift: 1.9,
    volatility: 14,
    sector: "Financials",
    change: 0.41,
    volume: "₹2,080 Cr",
    breadth: "Private banks steady",
    sentiment: "Mean-reversion setups dominate",
  },
  ICICIBANK: {
    label: "ICICI Bank",
    basePrice: 1128,
    drift: 2.1,
    volatility: 15,
    sector: "Financials",
    change: 1.04,
    volume: "₹1,930 Cr",
    breadth: "Financials leading",
    sentiment: "Breakout-ready with high participation",
  },
  SBIN: {
    label: "State Bank of India",
    basePrice: 812,
    drift: 1.4,
    volatility: 12,
    sector: "Financials",
    change: 0.58,
    volume: "₹1,220 Cr",
    breadth: "PSU banks firm",
    sentiment: "Momentum positive but extended intraday",
  },
};

const STRATEGY_TEMPLATES: Record<string, [string, string, number, string][]> = {
  NIFTY50: [
    ["Opening Range Breakout", "Bullish", 0.76, "Range high cleared with broad participation."],
    ["VWAP Reversion", "Neutral", 0.52, "Index is holding above VWAP without stretch."],
    ["Intraday Momentum", "Bullish", 0.73, "Higher highs with positive market breadth."],
    ["Relative Strength", "Bullish", 0.68, "Banks and energy are carrying the tape."],
    ["Volatility Squeeze", "Watch", 0.61, "Compression broke higher during the afternoon."],
    ["Volume Spike Reversal", "Inactive", 0.28, "No exhaustion move in benchmark flow."],
    ["Regime Classifier", "Trending", 0.84, "ADX and participation favor trend-following."],
  ],
  RELIANCE: [
    ["Opening Range Breakout", "Bullish", 0.81, "Held above the first 15-minute range."],
    ["VWAP Reversion", "Watch", 0.59, "Pullbacks to VWAP are being bought."],
    ["Intraday Momentum", "Bullish", 0.78, "Momentum stack remains positive."],
    ["Relative Strength", "Bullish", 0.74, "Outperforming NIFTY and sector peers."],
    ["Volatility Squeeze", "Watch", 0.63, "Expansion risk remains for the last hour."],
    ["Volume Spike Reversal", "Inactive", 0.31, "No capitulation candle detected."],
    ["Regime Classifier", "Trending", 0.86, "Trend regime active for large-cap energy."],
  ],
  TCS: [
    ["Opening Range Breakout", "Watch", 0.57, "Above open but not cleanly impulsive."],
    ["VWAP Reversion", "Neutral", 0.54, "Balanced around VWAP."],
    ["Intraday Momentum", "Bullish", 0.69, "Trend is intact but pace has slowed."],
    ["Relative Strength", "Bullish", 0.66, "IT basket improving relative strength."],
    ["Volatility Squeeze", "Watch", 0.62, "Tight hourly compression."],
    ["Volume Spike Reversal", "Inactive", 0.26, "No exhaustion signature."],
    ["Regime Classifier", "Normal", 0.72, "Trend bias with mixed breadth."],
  ],
  INFY: [
    ["Opening Range Breakout", "Inactive", 0.34, "Failed to hold opening extension."],
    ["VWAP Reversion", "Bullish", 0.67, "Range-bound tape favors reversion."],
    ["Intraday Momentum", "Neutral", 0.48, "Momentum lacks confirmation."],
    ["Relative Strength", "Weak", 0.39, "Lagging the benchmark on the day."],
    ["Volatility Squeeze", "Watch", 0.58, "Compression setup building."],
    ["Volume Spike Reversal", "Bullish", 0.64, "Late sell spike was absorbed."],
    ["Regime Classifier", "Range-Bound", 0.77, "Low ADX regime favors mean reversion."],
  ],
  HDFCBANK: [
    ["Opening Range Breakout", "Inactive", 0.42, "Opening move faded quickly."],
    ["VWAP Reversion", "Bullish", 0.71, "Clean reversion profile around VWAP."],
    ["Intraday Momentum", "Neutral", 0.46, "Trend signal is weak."],
    ["Relative Strength", "Watch", 0.55, "Private bank basket is stable."],
    ["Volatility Squeeze", "Inactive", 0.33, "No squeeze expansion."],
    ["Volume Spike Reversal", "Bullish", 0.68, "Buyer response on lower wick candle."],
    ["Regime Classifier", "Range-Bound", 0.8, "Low-volatility mean-reversion regime."],
  ],
  ICICIBANK: [
    ["Opening Range Breakout", "Bullish", 0.77, "Breakout sustained above range high."],
    ["VWAP Reversion", "Watch", 0.56, "Only valid on shallow pullback."],
    ["Intraday Momentum", "Bullish", 0.74, "Trend and participation aligned."],
    ["Relative Strength", "Bullish", 0.71, "Leading the financial complex."],
    ["Volatility Squeeze", "Bullish", 0.69, "Compression resolved higher."],
    ["Volume Spike Reversal", "Inactive", 0.24, "No reversal condition."],
    ["Regime Classifier", "Trending", 0.82, "Trend regime supports breakout tactics."],
  ],
  SBIN: [
    ["Opening Range Breakout", "Watch", 0.58, "Breakout attempt but follow-through mixed."],
    ["VWAP Reversion", "Bullish", 0.66, "Intraday pullbacks keep reverting upward."],
    ["Intraday Momentum", "Bullish", 0.65, "Momentum positive but less clean than private banks."],
    ["Relative Strength", "Watch", 0.57, "PSU basket still constructive."],
    ["Volatility Squeeze", "Inactive", 0.36, "No compression signal."],
    ["Volume Spike Reversal", "Neutral", 0.44, "No clear exhaustion edge."],
    ["Regime Classifier", "Normal", 0.69, "Moderate trend with choppier tape."],
  ],
};

import { HistoryPoint, Instrument, Strategy } from './types/market';

function hashCode(value: string): number {
  return Array.from(value).reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0);
}

function createSeries(symbol: string, range: string): HistoryPoint[] {
  const cfg = SYMBOL_CONFIG[symbol];
  const points = RANGE_POINTS[range];
  const step = RANGE_STEP[range];
  const now = Math.floor(Date.now() / 1000);
  const seed = hashCode(`${symbol}-${range}`);
  let price = cfg.basePrice;

  return Array.from({ length: points }, (_, index) => {
    const directional = Math.sin((index + seed) / 3.7) * cfg.volatility * 0.18;
    const drift = cfg.drift * (index / points);
    const noise = Math.cos((index + seed) / 5.1) * cfg.volatility * 0.08;
    const close = Number((price + directional + drift + noise).toFixed(2));
    const open = Number((close - Math.sin((index + seed) / 2.4) * cfg.volatility * 0.12).toFixed(2));
    const high = Number((Math.max(open, close) + cfg.volatility * 0.14).toFixed(2));
    const low = Number((Math.min(open, close) - cfg.volatility * 0.14).toFixed(2));
    const time = now - (points - index) * step;
    price = close;

    return { time, open, high, low, close, volume: Math.floor(Math.random() * 100000) };
  });
}

export const MARKET_SYMBOLS: Instrument[] = Object.keys(SYMBOL_CONFIG).map((symbol) => {
  const cfg = SYMBOL_CONFIG[symbol];
  const chart = {
    day: createSeries(symbol, "day"),
    month: createSeries(symbol, "month"),
    year: createSeries(symbol, "year"),
  };
  const last = chart.day[chart.day.length - 1];
  const previous = chart.day[chart.day.length - 2] ?? last;

  const strategies: Strategy[] = STRATEGY_TEMPLATES[symbol].map(([name, status, confidence, note]) => ({
    name,
    status,
    confidence,
    note
  }));

  return {
    symbol,
    label: cfg.label,
    lastPrice: last.close,
    change: cfg.change,
    change_pct: cfg.change,
    sector: cfg.sector,
    sentiment: cfg.sentiment,
    volume: cfg.volume,
    breadth: cfg.breadth,
    strategies
  };
});

export function getInstrument(symbol: string): Instrument {
  return MARKET_SYMBOLS.find((item) => item.symbol === symbol) ?? MARKET_SYMBOLS[0];
}

