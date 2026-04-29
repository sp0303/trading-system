import { Instrument, HistoryData, Benchmark, Signal, PaperAccount, PaperOrder, PaperPosition } from '../types/market';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''; // Dynamic Gateway Base

const normalizeRange = (range: string = '1D'): string => {
  const normalized = String(range).toUpperCase();
  if (normalized === 'DAY') return '1D';
  if (normalized === 'MONTH') return '1M';
  if (normalized === 'YEAR') return '1Y';
  return normalized;
};

export const fetchSymbols = async (): Promise<Instrument[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/symbols`);
    if (!response.ok) return [];
    const json = await response.json();
    if (json && json.status === 'success') return json.data || [];
    return [];
  } catch (err) {
    console.warn('Failed to fetch symbols:', err);
    return [];
  }
};

export const fetchHistory = async (symbol: string, range: string = '1D'): Promise<HistoryData> => {
  try {
    const response = await fetch(`${API_BASE_URL}/history?symbol=${symbol}&range=${normalizeRange(range)}`);
    if (!response.ok) throw new Error('History fetch failed');
    const json = await response.json();
    if (json && json.status === 'success') return json.data;
    throw new Error(json?.error || 'Failed to parse history');
  } catch (err) {
    console.warn('fetchHistory failed:', err);
    return { symbol, series: [] };
  }
};

export const fetchBenchmark = async (range: string = '1D'): Promise<Benchmark> => {
  try {
    const response = await fetch(`${API_BASE_URL}/benchmark?range=${normalizeRange(range)}`);
    if (!response.ok) throw new Error('Network response not ok');
    const json = await response.json();
    if (json && json.status === 'success' && json.data) {
      return {
        ...json.data,
        lastPrice: json.data.last_price,
        change: json.data.change_pct,
      };
    }
    throw new Error('Invalid benchmark data');
  } catch (err) {
    console.error('fetchBenchmark failed:', err);
    throw err; // Re-throw so Loader keeps showing or we handle it in UI
  }
};

export const fetchInsights = async (symbol: string): Promise<Instrument> => {
  try {
    const response = await fetch(`${API_BASE_URL}/insights?symbol=${symbol}`);
    if (!response.ok) throw new Error('Insights fetch failed');
    const json = await response.json();
    if (json && json.status === 'success') return json.data;
    throw new Error(json?.error || 'Failed to parse insights');
  } catch (err) {
    console.warn('fetchInsights failed:', err);
    throw err;
  }
};

export const fetchSignals = async (): Promise<Signal[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/signals`);
    if (!response.ok) return [];
    const json = await response.json();
    if (json && json.status === 'success') return json.data || [];
    return [];
  } catch (err) {
    console.warn('Failed to fetch signals:', err);
    return [];
  }
};

export const fetchNews = async (symbol?: string): Promise<any> => {
  try {
    const url = symbol ? `${API_BASE_URL}/news?symbol=${symbol}` : `${API_BASE_URL}/news`;
    const response = await fetch(url);
    if (!response.ok) return [];
    const json = await response.json();
    return json?.data || [];
  } catch (err) {
    console.warn('fetchNews failed:', err);
    return [];
  }
};

export const fetchFundamentals = async (symbol: string): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/fundamentals?symbol=${symbol}`);
    if (!response.ok) return null;
    const json = await response.json();
    return json?.data || null;
  } catch (err) {
    console.warn('fetchFundamentals failed:', err);
    return null;
  }
};

export const fetchAnalysis = async (symbol: string): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/analysis?symbol=${symbol}`);
    if (!response.ok) return null;
    const json = await response.json();
    return json?.data || json?.analysis || null;
  } catch (err) {
    console.warn('fetchAnalysis failed:', err);
    return null;
  }
};

export const fetchInstitutionalFlow = async (symbol: string): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/institutional-flow?symbol=${symbol}`);
    if (!response.ok) return null;
    const json = await response.json();
    return json?.data || null;
  } catch (err) {
    console.warn('fetchInstitutionalFlow failed:', err);
    return null;
  }
};

export const fetchSentiment = async (symbol: string): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/sentiment?symbol=${symbol}`);
    if (!response.ok) return null;
    const json = await response.json();
    return json?.data || null;
  } catch (err) {
    console.warn('fetchSentiment failed:', err);
    return null;
  }
};

export const triggerAIAnalysis = async (symbol: string, context: any): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/ai-analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol, context })
    });
    const json = await response.json();
    if (json && json.status === 'success') return json.data;
    throw new Error(json?.error || 'AI Analysis failed');
  } catch (err) {
    console.error('triggerAIAnalysis failed:', err);
    return { analysis: 'Analysis unavailable.' };
  }
};

// Paper Trading APIs
export const fetchPaperPositions = async (): Promise<PaperPosition[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/paper/positions`);
    const json = await response.json();
    return json && json.status === 'success' ? json.data : [];
  } catch (err) {
    console.warn('fetchPaperPositions failed:', err);
    return [];
  }
};

export const fetchPaperOrders = async (symbol?: string): Promise<PaperOrder[]> => {
  try {
    const url = symbol ? `${API_BASE_URL}/paper/orders?symbol=${symbol}` : `${API_BASE_URL}/paper/orders`;
    const response = await fetch(url);
    const json = await response.json();
    return json && json.status === 'success' ? json.data : [];
  } catch (err) {
    console.warn('fetchPaperOrders failed:', err);
    return [];
  }
};

export const createPaperOrder = async (orderData: any): Promise<PaperOrder> => {
  try {
    const response = await fetch(`${API_BASE_URL}/paper/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(orderData)
    });
    const json = await response.json();
    if (json && json.status === 'success') return json.data;
    throw new Error(json?.error || 'Failed to place paper order');
  } catch (err: any) {
    console.error('createPaperOrder failed:', err);
    throw err;
  }
};

export const closePaperPosition = async (symbol: string): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/paper/orders/${symbol}/close`, {
      method: 'POST'
    });
    const json = await response.json();
    if (json && json.status === 'success') return json.data;
    throw new Error(json?.error || 'Failed to close paper position');
  } catch (err: any) {
    console.error('closePaperPosition failed:', err);
    throw err;
  }
};

export const fetchPaperAccount = async (): Promise<PaperAccount> => {
  try {
    const response = await fetch(`${API_BASE_URL}/paper/account`);
    if (!response.ok) throw new Error('Account fetch failed');
    const json = await response.json();
    if (json && json.status === 'success') return json.data;
    throw new Error(json?.error || 'Failed to parse account');
  } catch (err) {
    console.warn('fetchPaperAccount failed:', err);
    // Return empty shell to avoid total crash
    return {
      total_equity: 0,
      available_cash: 0,
      invested_capital: 0,
      unrealized_pnl: 0,
      realized_pnl: 0,
    } as any;
  }
};
export const syncMarketData = async (force: boolean = false, symbol?: string): Promise<any> => {
  try {
    let url = `${API_BASE_URL}/sync?force=${force}`;
    if (symbol) url += `&symbol=${symbol}`;
    
    const response = await fetch(url, {
      method: 'POST'
    });
    const json = await response.json();
    return json;
  } catch (err) {
    console.error('syncMarketData failed:', err);
    throw err;
  }
};

export const fetchDailyPnl = async (): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/paper/daily-pnl`);
    if (!response.ok) return null;
    const json = await response.json();
    return json?.data || null;
  } catch (err) {
    console.warn('fetchDailyPnl failed:', err);
    return null;
  }
};

export const fetchDailyReport = async (date?: string): Promise<any> => {
  try {
    const url = date ? `${API_BASE_URL}/paper/reports/daily?date=${date}` : `${API_BASE_URL}/paper/reports/daily`;
    const response = await fetch(url);
    if (!response.ok) return null;
    const json = await response.json();
    return json?.data || null;
  } catch (err) {
    console.warn('fetchDailyReport failed:', err);
    return null;
  }
};

export const fetchModelPrediction = async (symbol: string, features: Record<string, any>): Promise<any> => {
  try {
    // 1. Extract and format timestamp (Mapping 'time' -> 'timestamp')
    const timestamp = String(features.time || features.timestamp || Math.floor(Date.now() / 1000));
    
    // 2. Sanitize features: Institutional Handoff (Strictly Numeric)
    const sanitizedFeatures: Record<string, number> = {};
    Object.entries(features).forEach(([key, value]) => {
      // Skip metadata and non-numeric fields
      if (['symbol', 'time', 'timestamp', 'sector', 'is_volume_spike'].includes(key)) return;
      
      // Ensure only valid numbers are passed
      const num = parseFloat(value);
      if (!isNaN(num)) {
        sanitizedFeatures[key] = num;
      }
    });

    const response = await fetch(`${API_BASE_URL}/model/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        symbol, 
        timestamp, 
        features: sanitizedFeatures 
      })
    });
    const json = await response.json();
    return json?.data || null;
  } catch (err) {
    console.warn('fetchModelPrediction failed:', err);
    return null;
  }
};

