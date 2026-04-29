import React, { useEffect, useMemo, useState } from 'react';
import { Routes, Route, useNavigate, Link } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  CandlestickChart,
  Filter,
  Search,
  Shield,
  TrendingUp,
  LayoutDashboard,
  Wallet,
  Menu
} from 'lucide-react';

import Sidebar from './components/Sidebar';
import SignalCard from './components/SignalCard';
import TradingViewChart from './components/TradingViewChart';
import SignalsGallery from './components/SignalsGallery';
import ClockIST from './components/ClockIST';
import StockPage from './pages/StockPage';
import PaperPortfolio from './pages/PaperPortfolio';
import Loader from './components/Loader';
import StatusPill from './components/StatusPill';
import { fetchSymbols, fetchHistory, fetchBenchmark, fetchInsights, fetchSignals, fetchPaperPositions, fetchPaperAccount, syncMarketData } from './api/market';

import { Instrument, Benchmark, Signal, HistoryPoint, Breadth, PaperPosition, PaperAccount } from './types/market';
import './App.css';

const RANGE_OPTIONS = [
  { id: 'day', label: '1D' },
  { id: 'month', label: '1M' },
  { id: 'year', label: '1Y' },
];

const STATUS_COLOR: Record<string, string> = {
  Bullish: 'var(--success-color)',
  Trending: 'var(--success-color)',
  Watch: 'var(--warning-color)',
  Neutral: 'var(--text-secondary)',
  Weak: 'var(--error-color)',
  Inactive: 'var(--text-muted)',
  'Range-Bound': 'var(--accent-color)',
  Normal: 'var(--accent-color)',
};

function formatPrice(value: number | undefined): string {
  if (value === undefined) return 'N/A';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(value);
}

function formatBreadth(breadth: Breadth | string | undefined): string {
  if (!breadth) return 'N/A';
  if (typeof breadth === 'string') return breadth;
  if (typeof breadth === 'object') {
    if (breadth.advancers != null && breadth.decliners != null) {
      return `${breadth.advancers} adv / ${breadth.decliners} dec`;
    }
    return 'Unavailable';
  }
  return 'N/A';
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [universe, setUniverse] = useState<Instrument[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [query, setQuery] = useState<string>('');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('RELIANCE');
  const [timeRange, setTimeRange] = useState<string>('day');
  const [benchmark, setBenchmark] = useState<Benchmark | null>(null);
  const [selectedInstrument, setSelectedInstrument] = useState<Instrument | null>(null);
  const [chartData, setChartData] = useState<HistoryPoint[]>([]);
  const [paperPositions, setPaperPositions] = useState<PaperPosition[]>([]);
  const [paperAccount, setPaperAccount] = useState<PaperAccount | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);




  useEffect(() => {
    const initLoad = async () => {
      try {
        const [syms, bench] = await Promise.all([
          fetchSymbols(),
          fetchBenchmark('1D')
        ]);
        setUniverse(syms);
        setBenchmark(bench);
        // On first load, if NIFTY50 is selected, set it up
        if (selectedSymbol === 'RELIANCE') {
           const reliance = syms.find(s => s.symbol === 'RELIANCE');
           if (reliance) {
             setSelectedInstrument(reliance);
             // We'll let loadDetails handle the chart data
           }
        }
      } catch (err) {
        console.error('Initial load failed:', err);
      }
    };
    initLoad();
  }, []); // Only on mount

  const loadSignals = async () => {
    setIsRefreshing(true);
    try {
      const [sigData, posData, accData] = await Promise.all([
        fetchSignals(),
        fetchPaperPositions(),
        fetchPaperAccount()
      ]);
      setSignals(sigData);
      setPaperPositions(posData);
      setPaperAccount(accData);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to fetch dashboard data:', err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  const loadDetails = async () => {
    if (!selectedSymbol) return;
    setIsRefreshing(true);
    try {
      if (selectedSymbol === 'NIFTY50') {
        const bench = await fetchBenchmark(timeRange === 'day' ? '1D' : timeRange === 'month' ? '1M' : '1Y');
        setBenchmark(bench);
        setSelectedInstrument(bench);
        setChartData(bench.series);
      } else {
        const [insights, history] = await Promise.all([
          fetchInsights(selectedSymbol),
          fetchHistory(selectedSymbol, timeRange === 'day' ? '1D' : timeRange === 'month' ? '1M' : '1Y')
        ]);
        setSelectedInstrument(insights);
        setChartData(history.series);
      }
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to fetch details:', err);
    } finally {
      setIsRefreshing(false);
    }
  };



  useEffect(() => {
    loadSignals();
  }, []);

  useEffect(() => {
    loadDetails();
  }, [selectedSymbol, timeRange]);
  
  const handleSync = async () => {
    setIsSyncing(true);
    try {
      // Pass force=true to bypass 2min threshold
      await syncMarketData(true);
      
      // UX Delay + Background Refetch
      setTimeout(async () => {
        await Promise.all([loadSignals(), loadDetails()]);
        setIsSyncing(false);
      }, 2500);
    } catch (err) {
      console.error("Sync failed:", err);
      setIsSyncing(false);
    }
  };


  const filteredUniverse = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return universe;
    return universe.filter((item) =>
      item.symbol.toLowerCase().includes(normalized) ||
      item.label.toLowerCase().includes(normalized) ||
      (item.sector && item.sector.toLowerCase().includes(normalized))
    );
  }, [query, universe]);

  const selectedSignals = useMemo(() => {
    if (!selectedInstrument) return [];
    return signals.filter((signal) => signal.symbol === selectedInstrument.symbol);
  }, [signals, selectedInstrument]);

  if (!selectedInstrument || !benchmark) {
    return <Loader text="Connecting to institutional backend..." />;
  }

  return (
    <div className="app-shell">
      {isRefreshing && (
        <div className="refresh-progress-bar">
          <div className="refresh-progress-fill active"></div>
        </div>
      )}
      <div className="top-nav">
        <div className="logo-group">
          <button 
            className="mobile-menu-btn" 
            onClick={() => setIsSidebarOpen(true)}
          >
            <Menu size={24} />
          </button>
          <div className="logo" style={{ display: 'flex', alignItems: 'center', gap: '12px', fontWeight: 'bold' }}>
            <TrendingUp size={24} color="var(--accent-color)" />
            <h1 style={{ margin: 0, fontSize: '20px' }}>Nifty <span className="hide-mobile">500 Elite</span></h1>
          </div>
        </div>
        
        <div className="nav-actions" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button 
            className={`sync-btn ${isSyncing ? 'loading' : ''}`}
            onClick={handleSync}
            disabled={isSyncing}
          >
            {isSyncing ? 'Syncing...' : 'Fetch Live'}
          </button>
          <StatusPill lastUpdated={lastUpdated} isRefreshing={isRefreshing} />
          <ClockIST />
        </div>
      </div>



      <Sidebar 
        activeTab="Dashboard" 
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onTabChange={(tab) => {
          if (tab === 'Dashboard') {
            navigate('/');
            window.scrollTo({ top: 0, behavior: 'smooth' });
          } else if (tab === 'Portfolio') {
            navigate('/paper-portfolio');
          } else if (tab === 'Signals') {
            navigate('/');
            setTimeout(() => {
              const el = document.getElementById('signals-gallery');
              if (el) el.scrollIntoView({ behavior: 'smooth' });
            }, 100);
          }
        }} 
        signalCount={signals.length} 
      />

      <div className="main-layout">


        
        <main className="content">
          <div className="summary-cards">
            <div className="summary-card">
              <div className="card-lbl">
                <Shield size={16} />
                <span>Market Regime</span>
              </div>
              <div className="card-val" style={{ color: benchmark?.status ? STATUS_COLOR[benchmark.status] : 'var(--text-secondary)' }}>
                {benchmark?.status || 'Active'}
              </div>
              <div className="card-sub">{benchmark?.label || 'NIFTY 50'}</div>
            </div>
            <div className="summary-card">
              <div className="card-lbl">
                <BarChart3 size={16} />
                <span>Index Breadth</span>
              </div>
              <div className="card-val">{formatBreadth(benchmark.breadth)}</div>
            </div>
            <div className="summary-card" onClick={() => navigate('/paper-portfolio')} style={{ cursor: 'pointer', border: '1px solid var(--accent-color)', background: 'rgba(99, 102, 241, 0.03)' }}>
              <div className="card-lbl">
                <Wallet size={16} />
                <span>Paper Portfolio</span>
              </div>
              <div className="card-val" style={{ color: 'var(--accent-color)' }}>
                ₹{(paperAccount?.total_equity || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div className="card-sub">{paperPositions.filter(p => p.net_qty !== 0).length} Open Assets · Net Worth</div>
            </div>
          </div>

          <div className="chart-and-widgets">
            <section className="chart-container card">
              <header className="widget-header">
                <div className="instr-meta" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div>
                    <h2>{selectedInstrument?.symbol || 'Select Asset'}</h2>
                    <span>{selectedInstrument?.label || ''}</span>
                  </div>
                  <button 
                    onClick={() => navigate(`/stock/${selectedSymbol}`)}
                    style={{
                      padding: '8px 16px',
                      background: 'var(--accent-color)',
                      color: 'white',
                      border: 'none',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      fontWeight: 'bold',
                      fontSize: '13px'
                    }}
                  >
                    Deep Dive Analysis →
                  </button>
                </div>
                <div className="range-selector">
                  {RANGE_OPTIONS.map(opt => (
                    <button 
                      key={opt.id}
                      className={timeRange === opt.id ? 'active' : ''}
                      onClick={() => setTimeRange(opt.id)}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </header>
              <TradingViewChart 
                data={chartData} 
                symbol={selectedInstrument?.symbol || 'NIFTY50'} 
                title={selectedInstrument?.symbol || 'NIFTY50'}
                subtitle={selectedInstrument?.label || 'NIFTY 50 Index'}
                rangeLabel={timeRange.toUpperCase()}
              />
            </section>

            <aside className="watchlist-container card">
              <div className="search-bar">
                <Search size={16} />
                <input 
                  type="text" 
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search symbols..." 
                />
              </div>
              <div className="watchlist">

                {filteredUniverse.map((instrument, idx) => (
                  <button 
                    key={`${instrument.symbol}-${idx}`}
                    className={`watchlist-item ${selectedSymbol === instrument.symbol ? 'active' : ''}`}
                    onClick={() => setSelectedSymbol(instrument.symbol)}
                  >
                    <div className="item-main" style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                      <strong style={{ display: 'block' }}>{instrument.symbol}</strong>
                      <span style={{ display: 'block', fontSize: '11px', opacity: 0.7 }}>{instrument.label}</span>
                    </div>
                    <div className="item-price">
                       <strong>{formatPrice(instrument.last_price || instrument.lastPrice)}</strong>
                       <span className={((instrument.change_pct ?? instrument.change) || 0) >= 0 ? 'pos' : 'neg'}>
                         {((instrument.change_pct ?? instrument.change) || 0) >= 0 ? '+' : ''}
                         {(instrument.change_pct ?? instrument.change) || 0}%
                       </span>
                    </div>
                  </button>
                ))}
              </div>
            </aside>
          </div>

          <SignalsGallery 
            signals={signals} 
            loading={loading} 
            onSelect={(symbol) => navigate(`/stock/${symbol}`)} 
            selectedSymbol={selectedSymbol} 
          />
        </main>
      </div>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/stock/:symbol" element={<StockPage />} />
      <Route path="/paper-portfolio" element={<PaperPortfolio />} />
    </Routes>
  );
};

export default App;
