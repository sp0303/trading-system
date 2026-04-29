import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  LucideLayoutDashboard, LucideTrendingUp, LucideNewspaper, LucideDatabase,
  LucideUsers, LucideMessageSquare, LucideActivity, LucideWallet, Menu,
  LucideChevronLeft, LucideBrainCircuit, LucideBarChart2, LucideZap
} from 'lucide-react';
import TradingViewChart from '../components/TradingViewChart';
import Sidebar from '../components/Sidebar';
import Loader from '../components/Loader';
import { Instrument, HistoryPoint, PaperPosition } from '../types/market';
import {
  fetchInsights, fetchHistory, fetchNews, fetchFundamentals, fetchAnalysis,
  fetchInstitutionalFlow, fetchSentiment, triggerAIAnalysis,
  fetchPaperPositions, closePaperPosition, fetchModelPrediction, syncMarketData
} from '../api/market';
import StatusPill from '../components/StatusPill';

// ─── RSI Gauge ──────────────────────────────────────────────────────────────
const RSIGauge: React.FC<{ value: number | null }> = ({ value }) => {
  if (value === null || value === undefined) return <span style={{ color: 'var(--text-muted)' }}>N/A</span>;
  const v = Math.max(0, Math.min(100, value));
  const color = v < 30 ? '#10b981' : v > 70 ? '#ef4444' : '#f59e0b';
  const label = v < 30 ? 'Oversold' : v > 70 ? 'Overbought' : 'Neutral';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{ flex: 1, height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', overflow: 'hidden', position: 'relative' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${v}%`, background: color, borderRadius: '3px', transition: 'width 0.5s ease' }} />
        <div style={{ position: 'absolute', left: '30%', top: '-2px', width: '1px', height: '10px', background: 'rgba(255,255,255,0.2)' }} />
        <div style={{ position: 'absolute', left: '70%', top: '-2px', width: '1px', height: '10px', background: 'rgba(255,255,255,0.2)' }} />
      </div>
      <span style={{ color, fontWeight: 700, fontSize: '12px', minWidth: '60px' }}>{v.toFixed(1)} <span style={{ fontWeight: 400, opacity: 0.8 }}>({label})</span></span>
    </div>
  );
};

// ─── Probability Bar ─────────────────────────────────────────────────────────
const ProbBar: React.FC<{ value: number | null; label: string }> = ({ value, label }) => {
  if (value === null || value === undefined) return null;
  const pct = (value * 100);
  const color = pct >= 60 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px', fontSize: '12px' }}>
        <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
        <span style={{ color, fontWeight: 700 }}>{pct.toFixed(1)}%</span>
      </div>
      <div style={{ height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: `linear-gradient(90deg, ${color}88, ${color})`, borderRadius: '4px', transition: 'width 0.8s ease' }} />
      </div>
    </div>
  );
};

// ─── Feature Row ─────────────────────────────────────────────────────────────
const FeatureRow: React.FC<{ label: string; value: any; unit?: string; color?: string }> = ({ label, value, unit = '', color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
    <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{label}</span>
    <strong style={{ fontSize: '13px', color: color || 'var(--text-primary)' }}>
      {value !== null && value !== undefined ? `${Number(value).toFixed(2)}${unit}` : 'N/A'}
    </strong>
  </div>
);


const StockPage: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>();
  const navigate = useNavigate();
  const [instrument, setInstrument] = useState<Instrument | null>(null);
  const [chartData, setChartData] = useState<HistoryPoint[]>([]);
  const [latestFeatures, setLatestFeatures] = useState<any>(null);
  const [news, setNews] = useState<any[]>([]);
  const [fundamentals, setFundamentals] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [instFlow, setInstFlow] = useState<any>(null);
  const [sentiment, setSentiment] = useState<any>(null);
  const [aiResult, setAiResult] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [paperPosition, setPaperPosition] = useState<PaperPosition | null>(null);
  const [modelPrediction, setModelPrediction] = useState<any>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const pageSize = 15;

  const [isSyncing, setIsSyncing] = useState(false);

  const loadAllData = async () => {
    if (!symbol) return;
    const isBackground = chartData.length > 0;
    if (!isBackground) setLoading(true);
    setIsRefreshing(true);
    try {
      const [insights, history, newsItems, fundamentalData, flowData, sentimentData, paperPosItems, analysisData] = await Promise.all([
        fetchInsights(symbol),
        fetchHistory(symbol, '1D'),
        fetchNews(symbol),
        fetchFundamentals(symbol),
        fetchInstitutionalFlow(symbol),
        fetchSentiment(symbol),
        fetchPaperPositions(),
        fetchAnalysis(symbol)
      ]);

      setInstrument(insights);
      setChartData(history.series);
      setNews(newsItems);
      setFundamentals(fundamentalData);
      setInstFlow(flowData);
      setSentiment(sentimentData);
      setAnalysis(analysisData);

      const currentPos = paperPosItems.find(p => p.symbol === symbol);
      setPaperPosition(currentPos || null);

      if (history.series && history.series.length > 0) {
        const lastPoint = history.series[history.series.length - 1];
        setLatestFeatures(lastPoint);
        if (lastPoint && !modelPrediction) { // Fetch if not already present
          const pred = await fetchModelPrediction(symbol, lastPoint as any);
          setModelPrediction(pred);
        }
      }

      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to load stock details:', err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadAllData();
  }, [symbol]);

  const handleSync = async () => {
    if (!symbol) return;
    setIsSyncing(true);
    try {
      await syncMarketData(true, symbol); // Force sync for specific symbol
      setTimeout(async () => {
        await loadAllData();
        setIsSyncing(false);
      }, 3000);
    } catch (err) {
      console.error("Sync failed:", err);
      setIsSyncing(false);
    }
  };

  const handleAIAnalysis = async () => {
    if (!symbol) return;
    setAiLoading(true);
    try {
      const context = {
        fundamentals: JSON.stringify({
          sector: fundamentals?.sector,
          pe: fundamentals?.pe_ratio,
          market_cap: fundamentals?.market_cap,
          business_summary: fundamentals?.long_summary?.slice(0, 300) + "..."
        }),
        news: JSON.stringify(news.slice(0, 5).map(n => ({
          title: n.title,
          summary: n.summary?.slice(0, 150) + "...",
          sentiment: n.sentiment_label,
          relevance: n.relevance_score
        }))),
        strategy_results: JSON.stringify(instrument?.strategies || []),
        institutional: JSON.stringify(instFlow),
        regime: instrument?.regime || 'Unknown',
        technicals_1h: JSON.stringify({
          rsi_14: latestFeatures?.rsi_14,
          macd_hist: latestFeatures?.macd_hist,
          adx_14: latestFeatures?.adx_14,
          vwap: latestFeatures?.vwap,
          bollinger_b: latestFeatures?.bollinger_b,
          close: latestFeatures?.close,
        }),
        model_prediction: JSON.stringify(modelPrediction)
      };
      const result = await triggerAIAnalysis(symbol, context);
      if (result && result.analysis) {
        setAiResult(result.analysis);
      } else {
        throw new Error("No analysis received from AI service.");
      }
    } catch (err: any) {
      setAiResult(`Analysis unavailable: ${err.message || "Unknown Error"}`);
    } finally {
      setAiLoading(false);
    }
  };

  const handleClosePosition = async () => {
    if (!symbol) return;
    try {
      await closePaperPosition(symbol);
      const posData = await fetchPaperPositions();
      const currentPos = posData.find(p => p.symbol === symbol);
      setPaperPosition(currentPos || null);
    } catch (err: any) {
      alert(`Failed to close position: ${err.message}`);
    }
  };

  if (loading) return <Loader text={`Loading full analysis for ${symbol}...`} />;
  if (!instrument) return <div className="app-shell error">Symbol {symbol} not found.</div>;

  // RSI color
  const rsi = latestFeatures?.rsi_14;
  const macdHist = latestFeatures?.macd_hist;
  const adx = latestFeatures?.adx_14;
  const bollingerB = latestFeatures?.bollinger_b;
  const vwap = latestFeatures?.vwap;
  const distVwap = latestFeatures?.distance_from_vwap;
  const volSpike = latestFeatures?.volume_spike_ratio;

  return (
    <div className="app-shell">
      {isRefreshing && (
        <div className="refresh-progress-bar">
          <div className="refresh-progress-fill active"></div>
        </div>
      )}
      <div className="top-nav">
        <div className="logo-group">
          <button className="mobile-menu-btn" onClick={() => setIsSidebarOpen(true)}><Menu size={24} /></button>
          <div className="logo" onClick={() => navigate('/')} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <LucideTrendingUp size={24} color="var(--accent-color)" />
            <h1 style={{ margin: 0, fontSize: '20px' }}>Nifty <span className="hide-mobile">500 Elite</span></h1>
          </div>
        </div>
        <div className="nav-links hide-mobile">
          <button onClick={() => navigate('/')}><LucideLayoutDashboard size={18} /> Dashboard</button>
        </div>
      </div>

      <Sidebar activeTab="" isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)}
        onTabChange={(tab) => { if (tab === 'Dashboard') navigate('/'); if (tab === 'Portfolio') navigate('/paper-portfolio'); }}
        signalCount={0} />

      <div className="main-layout">
        <main className="content stock-page-content">
          <header className="stock-header">
            <div className="back-btn" onClick={() => navigate('/')}>
              <LucideChevronLeft size={20} /> Back to Dashboard
            </div>
            <div className="header-flex">
              <div className="symbol-info">
                <h2>{instrument.symbol}</h2>
                <div className="meta-row">
                  <span>{instrument.label}</span>
                  {instrument.sector && <span className="sector-tag">{instrument.sector}</span>}
                  <StatusPill lastUpdated={lastUpdated} isRefreshing={isRefreshing} />
                </div>
              </div>
              <div className="price-display" style={{ textAlign: 'right' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', justifyContent: 'flex-end', marginBottom: '4px' }}>
                   <button 
                    className={`sync-btn-small ${isSyncing ? 'loading' : ''}`}
                    onClick={handleSync}
                    disabled={isSyncing}
                    style={{
                      padding: '4px 12px',
                      fontSize: '11px',
                      background: 'rgba(99,102,241,0.1)',
                      color: 'var(--accent-color)',
                      border: '1px solid var(--accent-light)',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontWeight: 600
                    }}
                  >
                    {isSyncing ? 'Syncing...' : 'Fetch Live'}
                  </button>
                  <span className="last-price">₹{instrument.last_price?.toLocaleString() || instrument.lastPrice?.toLocaleString()}</span>
                </div>
                <span className={((instrument.change_pct ?? instrument.change) || 0) >= 0 ? 'positive' : 'negative'}>
                  {((instrument.change_pct ?? instrument.change) || 0) >= 0 ? '+' : ''}
                  {(instrument.change_pct ?? instrument.change) || 0}%
                </span>
              </div>
            </div>
          </header>

          <div className="stock-grid">
            <div className="main-col">

              {/* ── Chart ──────────────────────────────────────────── */}
              <section className="chart-section card">
                <div className="card-header">
                  <h3><LucideTrendingUp size={18} /> Price Action</h3>
                </div>
                <div className="chart-container-detail">
                  <TradingViewChart data={chartData} symbol={instrument.symbol} title={instrument.symbol} subtitle={instrument.label} rangeLabel="1D" />
                </div>
              </section>

              {/* ── Technical Snapshot ─────────────────────────────── */}
              <section className="card" style={{ padding: '20px' }}>
                <div className="card-header" style={{ marginBottom: '16px' }}>
                  <h3><LucideBarChart2 size={18} /> Technical Snapshot</h3>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  {/* Left: Momentum */}
                  <div>
                    <p style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: '12px' }}>Momentum</p>
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '12px' }}>
                        <span style={{ color: 'var(--text-secondary)' }}>RSI-14</span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>(30 oversold / 70 overbought)</span>
                      </div>
                      <RSIGauge value={rsi} />
                    </div>
                    <FeatureRow label="MACD Histogram" value={macdHist} color={macdHist > 0 ? '#10b981' : '#ef4444'} />
                    <FeatureRow label="ADX Trend Strength" value={adx} color={adx > 25 ? '#6366f1' : 'var(--text-secondary)'} />
                    <FeatureRow label="Stoch %K" value={latestFeatures?.stoch_k_14} />
                    <FeatureRow label="Bollinger %B" value={bollingerB} color={bollingerB > 0.8 ? '#ef4444' : bollingerB < 0.2 ? '#10b981' : 'var(--text-primary)'} />
                  </div>
                  {/* Right: Volume & Price */}
                  <div>
                    <p style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: '12px' }}>Volume & Price Context</p>
                    <FeatureRow label="VWAP" value={vwap} unit="₹" />
                    <FeatureRow
                      label="Distance from VWAP"
                      value={distVwap}
                      unit="%"
                      color={distVwap > 0 ? '#10b981' : '#ef4444'}
                    />
                    <FeatureRow label="Volume Spike Ratio" value={volSpike} color={volSpike > 2 ? '#f59e0b' : 'var(--text-primary)'} />
                    <FeatureRow label="Relative Volume (20)" value={latestFeatures?.rvol_20} />
                    <FeatureRow label="ATR-14" value={latestFeatures?.atr_14} />
                    <FeatureRow label="CMF-20" value={latestFeatures?.cmf_20} color={latestFeatures?.cmf_20 > 0 ? '#10b981' : '#ef4444'} />
                  </div>
                </div>
                {/* Interpretation Banner */}
                {rsi !== null && adx !== null && (
                  <div style={{ marginTop: '16px', padding: '10px 14px', borderRadius: '8px', background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    📊 <strong style={{ color: 'var(--text-primary)' }}>Reading:</strong>{' '}
                    {rsi < 30 ? 'Oversold zone — potential bounce.' : rsi > 70 ? 'Overbought — watch for reversal.' : 'Neutral momentum.'}{' '}
                    {adx > 25 ? `Strong trend detected (ADX ${adx?.toFixed(0)}).` : 'No strong trend currently.'}{' '}
                    {macdHist > 0 ? 'MACD bullish crossover.' : 'MACD bearish / no crossover.'}
                  </div>
                )}
              </section>

              {/* ── Institutional Pros & Cons ── */}
              {analysis && (analysis.pros || analysis.cons) && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
                  {/* Pros */}
                  <div style={{ 
                    padding: '24px', 
                    borderRadius: '12px', 
                    background: 'rgba(16,185,129,0.03)', 
                    border: '1px solid rgba(16,185,129,0.2)',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.03)'
                  }}>
                    <h4 style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                      <span style={{ fontSize: '18px' }}>★</span> Institutional Pros
                    </h4>
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                      {analysis.pros?.map((pro: string, idx: number) => (
                        <li key={idx} style={{ fontSize: '13px', color: 'var(--text-main)', marginBottom: '10px', display: 'flex', alignItems: 'flex-start', gap: '10px', lineHeight: '1.5' }}>
                          <span style={{ color: '#10b981', marginTop: '2px', fontSize: '14px' }}>•</span> {pro}
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Cons */}
                  <div style={{ 
                    padding: '24px', 
                    borderRadius: '12px', 
                    background: 'rgba(239,68,68,0.03)', 
                    border: '1px solid rgba(239,68,68,0.2)',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.03)'
                  }}>
                    <h4 style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>
                      <span style={{ fontSize: '18px' }}>‼</span> Critical Cons
                    </h4>
                    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                      {analysis.cons?.map((con: string, idx: number) => (
                        <li key={idx} style={{ fontSize: '13px', color: 'var(--text-main)', marginBottom: '10px', display: 'flex', alignItems: 'flex-start', gap: '10px', lineHeight: '1.5' }}>
                          <span style={{ color: '#ef4444', marginTop: '2px', fontSize: '14px' }}>•</span> {con}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* ── ML Model Analysis ────────────────────────────── */}
              <section className="card" style={{ padding: '20px' }}>
                <div className="card-header" style={{ marginBottom: '16px' }}>
                  <h3><LucideBrainCircuit size={18} /> ML Ensemble Prediction</h3>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>7 trained models</span>
                </div>
                {(modelPrediction || instrument?.latest_model_prediction) ? (
                  <div>
                    {(() => {
                      const pred = modelPrediction || instrument?.latest_model_prediction;
                      return (
                        <>
                          <ProbBar value={pred.probability} label="Win Probability" />
                          <ProbBar value={pred.confidence} label="Model Confidence" />

                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '16px' }}>
                            <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(16,185,129,0.07)', border: '1px solid rgba(16,185,129,0.2)' }}>
                              <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '0 0 4px 0' }}>Expected Return (MFE)</p>
                              <strong style={{ fontSize: '18px', color: '#10b981' }}>+{(pred.expected_return).toFixed(2)}%</strong>
                            </div>
                            <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.2)' }}>
                              <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '0 0 4px 0' }}>Max Drawdown Risk (MAE)</p>
                              <strong style={{ fontSize: '18px', color: '#ef4444' }}>-{(Math.abs(pred.expected_drawdown)).toFixed(2)}%</strong>
                            </div>
                          </div>

                          {pred.is_anomaly && (
                            <div style={{ marginTop: '12px', padding: '8px 12px', borderRadius: '6px', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', fontSize: '12px', color: '#ef4444' }}>
                              ⚠️ <strong>Anomaly Detected</strong> — Market conditions are statistically unusual. Treat signals with extra caution.
                            </div>
                          )}

                          {pred.models_used && pred.models_used.length > 0 && (
                            <div style={{ marginTop: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
                              Models: {pred.models_used.join(' · ')}
                            </div>
                          )}
                        </>
                      );
                    })()}
                  </div>
                ) : (
                  <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                    <LucideBrainCircuit size={28} style={{ marginBottom: '8px', opacity: 0.4 }} />
                    <p>Model service loading or no features available yet.</p>
                    <p style={{ fontSize: '11px', marginTop: '4px' }}>Ensure the model service is running and ohlcv_enriched has recent data.</p>
                  </div>
                )}
              </section>

              {/* ── AI Decision Hub ─────────────────────────────── */}
              <section className="ai-decision-section card">
                <div className="card-header ai-header">
                  <div className="ai-title">
                    <LucideMessageSquare size={18} />
                    <h3>AI Decision Hub (Gemma)</h3>
                  </div>
                  <button
                    className={`gemma-analyze-btn ${aiLoading ? 'loading' : ''}`}
                    onClick={handleAIAnalysis}
                    disabled={aiLoading}
                  >
                    {aiLoading ? 'Gemma Thinking...' : 'Analyze with Gemma'}
                  </button>
                </div>
                <div className="ai-console">
                  {aiResult ? (
                    <div className="ai-response markdown-rendered">
                      {aiResult.split('\n').map((line, i) => <p key={i}>{line}</p>)}
                    </div>
                  ) : (
                    <p className="placeholder-text">Click the button for a real-time institutional analysis by Gemma. Uses RSI, MACD, Model predictions, News and Institutional flow as context.</p>
                  )}
                </div>
              </section>

              {/* ── Strategy Engine ─────────────────────────────── */}
              <section className="strategies-section card">
                <div className="card-header">
                  <h3><LucideActivity size={18} /> Strategy Engine (7-Model Status)</h3>
                </div>
                <div className="strategies-display-grid">
                  {instrument.strategies?.map((strat: any, i: number) => (
                    <div key={i} className="strategy-item-row" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '8px', padding: '16px' }}>
                      <div className="strat-top-row" style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                        <span className="strat-name" style={{ fontSize: '14px', fontWeight: 'bold' }}>{strat.name}</span>
                        <div className={`strat-status-pill ${strat.status?.toLowerCase().replace(' ', '-') || 'neutral'}`}>{strat.status || 'Neutral'}</div>
                      </div>
                      <div className="strat-note-box" style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4', background: 'rgba(255,255,255,0.02)', padding: '8px', borderRadius: '4px', width: '100%', borderLeft: '2px solid var(--accent-light)' }}>
                        {strat.note}
                      </div>
                      <span className="strat-time" style={{ fontSize: '10px', opacity: 0.6 }}>{strat.last_signal_time !== 'N/A' ? `Last Data: ${strat.last_signal_time.split(' ')?.[1]?.slice(0, 5) || strat.last_signal_time}` : 'Scanning...'}</span>
                    </div>
                  ))}
                </div>
              </section>

              {/* ── OHLCV Table ─────────────────────────────────── */}
              <section className="historical-data-section card">
                <div className="card-header">
                  <h3><LucideDatabase size={18} /> Historical Data (OHLCV)</h3>
                </div>
                <div className="table-responsive">
                  <table className="modern-table market-data-table">
                    <thead>
                      <tr>
                        <th>Time</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th><th>RSI</th><th>MACD</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        const slicedData = [...chartData].reverse().slice((currentPage - 1) * pageSize, currentPage * pageSize);
                        return slicedData.map((point: any, i: number) => (
                          <tr key={i}>
                            <td className="time-cell">
                              {typeof point.time === 'string' ? point.time : new Date(point.time * 1000).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                            </td>
                            <td className="price-cell">₹{point.open?.toFixed(2)}</td>
                            <td className="price-cell">₹{point.high?.toFixed(2)}</td>
                            <td className="price-cell">₹{point.low?.toFixed(2)}</td>
                            <td className="price-cell font-bold" style={{ color: point.close >= point.open ? 'var(--success-color)' : 'var(--error-color)' }}>₹{point.close?.toFixed(2)}</td>
                            <td className="volume-cell">{point.volume?.toLocaleString()}</td>
                            <td style={{ color: point.rsi_14 < 30 ? '#10b981' : point.rsi_14 > 70 ? '#ef4444' : 'var(--text-primary)', fontSize: '12px' }}>
                              {point.rsi_14 ? point.rsi_14.toFixed(1) : '—'}
                            </td>
                            <td style={{ color: point.macd_hist > 0 ? '#10b981' : '#ef4444', fontSize: '12px' }}>
                              {point.macd_hist ? point.macd_hist.toFixed(4) : '—'}
                            </td>
                          </tr>
                        ));
                      })()}
                      {chartData.length === 0 && (
                        <tr><td colSpan={8} style={{ textAlign: 'center', padding: '32px', opacity: 0.5 }}>No historical data available.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
                {chartData.length > pageSize && (
                  <div className="pagination-controls">
                    <button className="pagination-btn" onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}>Previous</button>
                    <span className="pagination-info">Page {currentPage} of {Math.ceil(chartData.length / pageSize)}</span>
                    <button className="pagination-btn" onClick={() => setCurrentPage(p => Math.min(Math.ceil(chartData.length / pageSize), p + 1))} disabled={currentPage >= Math.ceil(chartData.length / pageSize)}>Next</button>
                  </div>
                )}
              </section>
            </div>

            {/* ── Side Panels ────────────────────────────────────── */}
            <div className="side-panels">

              {/* Paper Position */}
              {paperPosition && paperPosition.net_qty !== 0 && (
                <section className="paper-position-section card highlight">
                  <div className="card-header">
                    <h3><LucideWallet size={18} /> Paper Position</h3>
                  </div>
                  <div className="stats-grid-compact highlight-box">
                    <div className="stat-row"><span>Net Qty</span><strong style={{ color: paperPosition.net_qty >= 0 ? '#10b981' : '#ef4444' }}>{paperPosition.net_qty} {paperPosition.net_qty > 0 ? '▲ LONG' : '▼ SHORT'}</strong></div>
                    <div className="stat-row"><span>Avg Price</span><strong>₹{paperPosition.avg_price?.toFixed(2)}</strong></div>
                    <div className="stat-row"><span>Unrealized PnL</span><strong style={{ color: paperPosition.unrealized_pnl >= 0 ? '#10b981' : '#ef4444' }}>₹{paperPosition.unrealized_pnl?.toFixed(2)}</strong></div>
                    <div className="stat-row"><span>Realized PnL</span><strong>₹{paperPosition.realized_pnl?.toFixed(2)}</strong></div>
                    <button className="close-pos-btn-modern" onClick={handleClosePosition} style={{ marginTop: '12px', width: '100%', padding: '10px', background: 'rgba(239,68,68,0.1)', color: 'var(--error-color)', border: '1px solid var(--error-color)', borderRadius: '8px', fontWeight: '700', fontSize: '13px', cursor: 'pointer' }}>
                      Close Position
                    </button>
                  </div>
                </section>
              )}

              {/* Sentiment */}
              <section className="card" style={{ padding: '16px' }}>
                <div className="card-header" style={{ marginBottom: '12px' }}>
                  <h3 style={{ fontSize: '14px' }}><LucideZap size={16} /> Market Sentiment</h3>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <div style={{ padding: '10px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', textAlign: 'center' }}>
                    <p style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '0 0 4px 0' }}>News Sentiment</p>
                    <strong style={{ fontSize: '13px', color: sentiment?.label?.includes('Bull') ? '#10b981' : sentiment?.label?.includes('Bear') ? '#ef4444' : 'var(--text-primary)' }}>
                      {sentiment?.label || 'N/A'}
                    </strong>
                    <p style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>Score: {sentiment?.score?.toFixed(3) || '—'}</p>
                  </div>
                  <div style={{ padding: '10px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', textAlign: 'center' }}>
                    <p style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '0 0 4px 0' }}>Headlines</p>
                    <strong style={{ fontSize: '22px', color: 'var(--accent-color)' }}>{sentiment?.headline_count || 0}</strong>
                    <p style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>analyzed</p>
                  </div>
                </div>
              </section>

              {/* Fundamentals */}
              <section className="fundamentals-section card">
                <div className="card-header"><h3><LucideDatabase size={18} /> Key Metrics</h3></div>
                <div className="stats-grid-compact">
                  <div className="stat-row"><span>PE Ratio</span><strong>{fundamentals?.pe_ratio?.toFixed(2) || 'N/A'}</strong></div>
                  <div className="stat-row"><span>Market Cap</span><strong>₹{(fundamentals?.market_cap / 1e7)?.toFixed(0) || 'N/A'} Cr</strong></div>
                  <div className="stat-row"><span>PB Ratio</span><strong>{fundamentals?.pb_ratio?.toFixed(2) || 'N/A'}</strong></div>
                  <div className="stat-row"><span>Div Yield</span><strong>{((fundamentals?.dividend_yield || 0) * 100).toFixed(2)}%</strong></div>
                  <div className="stat-row"><span>52W High</span><strong>₹{fundamentals?.high_52w?.toLocaleString() || 'N/A'}</strong></div>
                  <div className="stat-row"><span>52W Low</span><strong>₹{fundamentals?.low_52w?.toLocaleString() || 'N/A'}</strong></div>
                </div>
              </section>

              {/* Institutional Flow */}
              <section className="institutional-section card">
                <div className="card-header"><h3><LucideUsers size={18} /> Institutional Flow</h3></div>
                <div className="inst-flow-content" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 'bold', background: instFlow?.signal?.sentiment?.includes('Bullish') ? 'rgba(16,185,129,0.1)' : 'rgba(148,163,184,0.1)', color: instFlow?.signal?.sentiment?.includes('Bullish') ? '#10b981' : '#94a3b8' }}>
                      {instFlow?.signal?.sentiment || 'Neutral'}
                    </div>
                    <div style={{ fontSize: '12px', opacity: 0.8 }}>Score: <strong>{instFlow?.signal?.score || 0}/5</strong></div>
                  </div>
                  <div>
                    <div style={{ marginBottom: '6px', fontSize: '13px' }}>Delivery Strength: <strong>{instFlow?.delivery?.percentage || 0}%</strong></div>
                    <div style={{ height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '5px', overflow: 'hidden' }}>
                      <div style={{ width: `${instFlow?.delivery?.percentage || 0}%`, height: '100%', background: 'linear-gradient(90deg, #6366f1, #a855f7)', transition: 'width 0.5s ease' }} />
                    </div>
                  </div>
                  {instFlow?.signal?.reasoning?.map((r: string, idx: number) => (
                    <div key={idx} style={{ fontSize: '11px', display: 'flex', gap: '6px' }}><span style={{ color: '#10b981' }}>•</span>{r}</div>
                  ))}
                </div>
              </section>

              {/* News */}
              <section className="news-section card">
                <div className="card-header"><h3><LucideNewspaper size={18} /> Latest News (RSS)</h3></div>
                <div className="news-feed">
                  {news.length > 0 ? news.slice(0, 8).map((item, idx) => (
                    <div className="news-item" key={idx} onClick={() => window.open(item.link, '_blank')}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                        <h4 style={{ margin: 0, paddingRight: '60px' }}>{item.title}</h4>
                        {item.sentiment_label && (
                          <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: item.sentiment_score > 0.05 ? 'rgba(16,185,129,0.15)' : item.sentiment_score < -0.05 ? 'rgba(239,68,68,0.15)' : 'rgba(148,163,184,0.15)', color: item.sentiment_score > 0.05 ? '#10b981' : item.sentiment_score < -0.05 ? '#ef4444' : '#94a3b8', fontWeight: 'bold', whiteSpace: 'nowrap' }}>
                            {item.sentiment_label}
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{item.published || 'Today'} • {item.source}</span>
                    </div>
                  )) : <p className="no-news">No recent news found for this symbol.</p>}
                </div>
              </section>

            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default StockPage;
