import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LucideLayoutDashboard,
  LucideTrendingUp,
  LucideWallet,
  LucideHistory,
  LucideActivity,
  LucideArrowUpRight,
  LucideArrowDownRight,
  LucideChevronLeft,
  LucideCircleDollarSign,
  LucidePieChart,
  LucideClock,
  LucideCalendarCheck,
  LucideDownload,
  LucideRefreshCw,
  LucideSearch,
  LucideFilter,
  LucideBarChart4,
  LucideArrowRightLeft,
  Menu
} from 'lucide-react';

import Sidebar from '../components/Sidebar';
import Loader from '../components/Loader';
import ClockIST from '../components/ClockIST';
import { PaperPosition, PaperOrder, PaperAccount } from '../types/market';
import { fetchPaperPositions, fetchPaperOrders, fetchPaperAccount, closePaperPosition, fetchDailyPnl, fetchDailyReport } from '../api/market';
import StatusPill from '../components/StatusPill';

const PaperPortfolio: React.FC = () => {
  const navigate = useNavigate();
  const [positions, setPositions] = useState<PaperPosition[]>([]);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [dailyPnl, setDailyPnl] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [reportDate, setReportDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [reportData, setReportData] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [strategyFilter, setStrategyFilter] = useState('All');


  const handleClose = async (symbol: string) => {
    try {
      setLoading(true);
      await closePaperPosition(symbol);
      await loadPortfolioData();
    } catch (err: any) {
      alert(`Close failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadPortfolioData = async () => {
    setIsRefreshing(true);
    try {
      const [posData, orderData, accData, pnlData, report] = await Promise.all([
        fetchPaperPositions(),
        fetchPaperOrders(),
        fetchPaperAccount(),
        fetchDailyPnl(),
        fetchDailyReport(reportDate)
      ]);
      setPositions(posData);
      setOrders(orderData);
      setAccount(accData);
      setDailyPnl(pnlData);
      setReportData(report);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to load portfolio:', err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadPortfolioData();
  }, [reportDate]);

  const handleExport = () => {
    if (!reportData || !reportData.trades || reportData.trades.length === 0) {
      alert('No trades to export.');
      return;
    }

    const headers = ['Symbol', 'Type', 'Qty', 'Entry Price', 'Exit Price', 'PnL', 'Strategy', 'Status', 'Time'];
    const csvRows = [
      headers.join(','),
      ...reportData.trades.map((t: any) => [
        t.symbol,
        t.side,
        t.qty,
        t.entry_price,
        t.exit_price || '-',
        t.pnl,
        t.strategy,
        t.status,
        t.time
      ].map(val => `"${val}"`).join(','))
    ];

    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `trading_report_${reportDate}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };


  if (loading) {
    return <Loader text="Synchronizing institutional portfolio metrics..." />;
  }

  const formatCurrency = (val: number) => 
    new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(val);

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
          <div className="logo" onClick={() => navigate('/')} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <LucideTrendingUp size={24} color="var(--accent-color)" />
            <h1 style={{ margin: 0, fontSize: '20px' }}>Nifty <span className="hide-mobile">500 Elite</span></h1>
          </div>
        </div>
        <div className="nav-actions" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <StatusPill lastUpdated={lastUpdated} isRefreshing={isRefreshing} />
          <ClockIST />
        </div>
      </div>


      <Sidebar 
        activeTab="Portfolio" 
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onTabChange={(tab) => {
          if (tab === 'Dashboard') navigate('/');
        }} 
        signalCount={0} 
      />

      <div className="main-layout">


        
        <main className="content portfolio-content">
          <header className="portfolio-header-advanced">
            <div className="header-top">
              <div className="back-btn-modern" onClick={() => navigate('/')}>
                <LucideChevronLeft size={18} /> Dashboard
              </div>
              <div className="portfolio-title-group">
                <h2>Paper Portfolio</h2>
              </div>
            </div>
            
            <div className="stats-ribbon">
              <div className="stat-premium-card glass">
                <div className="card-icon" style={{ background: 'rgba(99, 102, 241, 0.15)', color: 'var(--accent-color)' }}>
                  <LucideWallet size={20} />
                </div>
                <div className="card-info">
                  <span className="card-label">Available Cash</span>
                  <strong className="card-value">{formatCurrency(account?.available_cash || 0)}</strong>
                </div>
              </div>

              <div className="stat-premium-card glass">
                <div className="card-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
                  <LucideCircleDollarSign size={20} />
                </div>
                <div className="card-info">
                  <span className="card-label">Invested Capital</span>
                  <strong className="card-value">{formatCurrency(account?.invested_capital || 0)}</strong>
                </div>
              </div>

              <div className="stat-premium-card glass">
                <div className="card-icon" style={{ background: account?.unrealized_pnl && account.unrealized_pnl >= 0 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)', color: account?.unrealized_pnl && account.unrealized_pnl >= 0 ? 'var(--success-color)' : 'var(--error-color)' }}>
                  <LucidePieChart size={20} />
                </div>
                <div className="card-info">
                  <span className="card-label">Unrealized PnL</span>
                  <strong className="card-value" style={{ color: account?.unrealized_pnl && account.unrealized_pnl >= 0 ? 'var(--success-color)' : 'var(--error-color)' }}>
                    {account?.unrealized_pnl && account.unrealized_pnl >= 0 ? '+' : ''}{formatCurrency(account?.unrealized_pnl || 0)}
                  </strong>
                </div>
              </div>

              <div className="stat-premium-card glass highlight-equity">
                <div className="card-info">
                  <span className="card-label">Total Equity</span>
                  <strong className="card-value">{formatCurrency(account?.total_equity || 0)}</strong>
                </div>
                <div className="equity-progress">
                  <div className="progress-bar" style={{ width: '100%' }}></div>
                </div>
              </div>
            </div>
          </header>

          <div className="portfolio-grid-advanced">

            {/* ── Today's Performance ─────────────────────────── */}
            <section className="card" style={{ padding: '20px', marginBottom: '0' }}>
              <div className="section-header-modern" style={{ marginBottom: '16px' }}>
                <h3><LucideCalendarCheck size={18} /> Today's Performance</h3>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{dailyPnl?.date || 'N/A'}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '0 0 6px 0', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Realized P&L</p>
                  <strong style={{ fontSize: '20px', color: (dailyPnl?.realized_pnl || 0) >= 0 ? '#10b981' : '#ef4444' }}>
                    {(dailyPnl?.realized_pnl || 0) >= 0 ? '+' : ''}₹{(dailyPnl?.realized_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </strong>
                  <p style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>Booked profits/losses</p>
                </div>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '0 0 6px 0', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Unrealized P&L</p>
                  <strong style={{ fontSize: '20px', color: (dailyPnl?.unrealized_pnl || 0) >= 0 ? '#10b981' : '#ef4444' }}>
                    {(dailyPnl?.unrealized_pnl || 0) >= 0 ? '+' : ''}₹{(dailyPnl?.unrealized_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </strong>
                  <p style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>Open positions MTM</p>
                </div>
                <div style={{ padding: '14px', borderRadius: '10px', background: (dailyPnl?.total_pnl || 0) >= 0 ? 'rgba(16,185,129,0.07)' : 'rgba(239,68,68,0.07)', border: `1px solid ${(dailyPnl?.total_pnl || 0) >= 0 ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'}` }}>
                  <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '0 0 6px 0', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Day P&L</p>
                  <strong style={{ fontSize: '22px', color: (dailyPnl?.total_pnl || 0) >= 0 ? '#10b981' : '#ef4444' }}>
                    {(dailyPnl?.total_pnl || 0) >= 0 ? '+' : ''}₹{(dailyPnl?.total_pnl || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </strong>
                </div>
                <div style={{ padding: '14px', borderRadius: '10px', background: 'rgba(99,102,241,0.07)', border: '1px solid rgba(99,102,241,0.2)' }}>
                  <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '0 0 6px 0', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Trades Today</p>
                  <strong style={{ fontSize: '22px', color: 'var(--accent-color)' }}>{dailyPnl?.trades_today || 0}</strong>
                  <p style={{ fontSize: '10px', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>{dailyPnl?.open_positions || 0} open positions</p>
                </div>
              </div>
            </section>

            <section className="positions-section-modern card">
              <div className="section-header-modern">
                <h3><LucideActivity size={18} /> Open Positions</h3>
                <span className="count-pill">{positions.filter(p => p.net_qty !== 0).length} Assets</span>
              </div>
              <div className="table-responsive">
                <table className="modern-table desktop-only">
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th>Quantity</th>
                      <th className="hide-tablet">Avg Price</th>
                      <th className="hide-tablet">Market Price</th>
                      <th>Unrealized PnL</th>
                      <th className="hide-tablet">ROI</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.filter(p => p.net_qty !== 0).map((pos, i) => {
                      const roi = (pos.unrealized_pnl / (Math.abs(pos.net_qty) * pos.avg_price)) * 100;
                      return (
                        <tr key={i} className="clickable-row" onClick={() => navigate(`/stock/${pos.symbol}`)}>
                          <td>
                            <div className="symbol-cell-modern">
                              <strong>{pos.symbol}</strong>
                              <span>National Stock Exchange</span>
                            </div>
                          </td>
                          <td>
                            <span className={`side-badge ${pos.net_qty > 0 ? 'long' : 'short'}`}>
                              {pos.net_qty > 0 ? 'LONG' : 'SHORT'}
                            </span>
                            <span className="qty-val">{Math.abs(pos.net_qty)} Units</span>
                          </td>
                          <td className="hide-tablet">₹{pos.avg_price.toLocaleString()}</td>
                          <td className="hide-tablet">₹{pos.last_price?.toLocaleString()}</td>
                          <td className={pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}>
                            {pos.unrealized_pnl >= 0 ? '+' : ''}₹{pos.unrealized_pnl.toFixed(2)}
                          </td>
                          <td className={pos.unrealized_pnl >= 0 ? 'positive' : 'negative'} className="hide-tablet">
                            {pos.unrealized_pnl >= 0 ? '+' : ''}{roi.toFixed(2)}%
                          </td>
                          <td onClick={(e) => e.stopPropagation()}>
                             <button 
                               onClick={() => handleClose(pos.symbol)}
                               style={{
                                 padding: '6px 12px',
                                 fontSize: '11px',
                                 background: 'rgba(239, 68, 68, 0.1)',
                                 color: 'var(--error-color)',
                                 border: '1px solid var(--error-color)',
                                 borderRadius: '6px',
                                 fontWeight: '600',
                                 cursor: 'pointer'
                               }}
                             >
                               Close
                             </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                <div className="mobile-only-cards">
                  {positions.filter(p => p.net_qty !== 0).map((pos, i) => {
                    const roi = (pos.unrealized_pnl / (Math.abs(pos.net_qty) * pos.avg_price)) * 100;
                    return (
                      <div key={i} className="mobile-pos-card glass" onClick={() => navigate(`/stock/${pos.symbol}`)}>
                        <div className="card-top">
                          <div className="symbol-cell-modern">
                            <strong>{pos.symbol}</strong>
                            <span>NSE</span>
                          </div>
                          <span className={`side-badge ${pos.net_qty > 0 ? 'long' : 'short'}`}>
                            {pos.net_qty > 0 ? 'LONG' : 'SHORT'}
                          </span>
                        </div>
                        <div className="card-mid">
                          <div className="metric">
                            <span className="lbl">Qty</span>
                            <span className="val">{Math.abs(pos.net_qty)}</span>
                          </div>
                          <div className="metric">
                            <span className="lbl">PnL</span>
                            <span className={`val ${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}`}>
                              {pos.unrealized_pnl >= 0 ? '+' : ''}₹{pos.unrealized_pnl.toFixed(2)}
                            </span>
                          </div>
                          <div className="metric">
                            <span className="lbl">ROI</span>
                            <span className={`val ${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}`}>
                              {pos.unrealized_pnl >= 0 ? '+' : ''}{roi.toFixed(2)}%
                            </span>
                          </div>
                        </div>
                        <button 
                          className="mobile-close-btn"
                          onClick={(e) => { e.stopPropagation(); handleClose(pos.symbol); }}
                        >
                          Close Position
                        </button>
                      </div>
                    );
                  })}
                </div>

                {positions.filter(p => p.net_qty !== 0).length === 0 && (
                  <div style={{ textAlign: 'center', padding: '48px', opacity: 0.5 }}>No active market exposure currently.</div>
                )}

              </div>
            </section>

            <section className="orders-section-modern card">
              <div className="section-header-modern">
                <h3><LucideHistory size={18} /> Recent Executions</h3>
              </div>
              <div className="execution-list">
                {orders.slice(0, 10).map((order, i) => (
                  <div key={i} className="execution-item">
                    <div className="exec-time">
                      <LucideClock size={12} />
                      {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                    <div className="exec-main">
                      <div className="exec-symbol">
                        <strong>{order.symbol}</strong>
                        <span className={order.side.toLowerCase()}>{order.side}</span>
                      </div>
                      <div className="exec-details">
                        <span>{order.qty} Units @ ₹{order.avg_fill_price?.toFixed(2)}</span>
                        <div className={`exec-status status-${(order.status || 'unknown').toLowerCase()}`}>
                          {order.status || 'UNKNOWN'}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>

          {/* ── Daily Trading Report ─────────────────────────── */}
          <div className="report-dashboard-container card glass" style={{ marginTop: '24px', padding: '24px' }}>
            <header className="report-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
              <div className="report-title">
                <h2 style={{ fontSize: '24px', margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <LucideBarChart4 color="var(--accent-color)" /> Daily Trading Report
                </h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '14px', margin: '4px 0 0 0' }}>Institutional execution analytics and trade auditing</p>
              </div>
              
              <div className="report-controls" style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <input 
                  type="date" 
                  value={reportDate}
                  onChange={(e) => setReportDate(e.target.value)}
                  style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', color: 'var(--text-primary)', padding: '8px 12px', borderRadius: '8px' }}
                />
                <button className="btn-icon" onClick={() => loadPortfolioData()} title="Refresh Report">
                  <LucideRefreshCw size={18} />
                </button>
                <button className="btn-secondary" onClick={handleExport} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <LucideDownload size={16} /> Export
                </button>
              </div>
            </header>

            {/* Report Summary Cards */}
            <div className="report-summary-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '32px' }}>
              <div className="report-stat-card glass">
                <span className="lbl">Win Rate</span>
                <strong className="val" style={{ color: (reportData?.summary?.win_rate || 0) >= 50 ? 'var(--success-color)' : 'var(--warning-color)' }}>
                  {reportData?.summary?.win_rate || 0}%
                </strong>
                <div className="progress-mini"><div style={{ width: `${reportData?.summary?.win_rate || 0}%`, background: 'var(--success-color)' }}></div></div>
              </div>
              <div className="report-stat-card glass">
                <span className="lbl">Net P&L</span>
                <strong className="val" style={{ color: (reportData?.summary?.net_pnl || 0) >= 0 ? 'var(--success-color)' : 'var(--error-color)' }}>
                  {formatCurrency(reportData?.summary?.net_pnl || 0)}
                </strong>
              </div>
              <div className="report-stat-card glass">
                <span className="lbl">Total Trades</span>
                <strong className="val">{reportData?.summary?.total_trades || 0}</strong>
              </div>
              <div className="report-stat-card glass">
                <span className="lbl">Gross Profit</span>
                <strong className="val" style={{ color: 'var(--success-color)' }}>{formatCurrency(reportData?.summary?.gross_profit || 0)}</strong>
              </div>
            </div>

            {/* Trades Table Section */}
            <section className="report-table-section">
              <div className="table-filters" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
                <div className="search-box glass" style={{ display: 'flex', alignItems: 'center', padding: '0 12px', borderRadius: '8px', border: '1px solid var(--border-color)', flex: 1, minWidth: '200px' }}>
                  <LucideSearch size={16} color="var(--text-muted)" />
                  <input 
                    placeholder="Search by stock symbol..." 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{ background: 'none', border: 'none', color: 'var(--text-primary)', padding: '10px', width: '100%', outline: 'none' }}
                  />
                </div>
                <div className="filter-group" style={{ display: 'flex', gap: '10px' }}>
                  <select 
                    className="glass-select"
                    value={strategyFilter}
                    onChange={(e) => setStrategyFilter(e.target.value)}
                    style={{ background: 'var(--bg-card)', color: 'var(--text-primary)', border: '1px solid var(--border-color)', padding: '0 12px', borderRadius: '8px' }}
                  >
                    <option value="All">All Strategies</option>
                    {reportData?.strategy_performance?.map((s: any) => <option key={s.name} value={s.name}>{s.name}</option>)}
                  </select>
                </div>
              </div>

              <div className="table-responsive glass" style={{ borderRadius: '12px', overflow: 'hidden' }}>
                <table className="modern-table">
                  <thead>
                    <tr>
                      <th>Symbol</th>
                      <th>Type</th>
                      <th>Qty</th>
                      <th>Entry</th>
                      <th>Exit</th>
                      <th>PnL</th>
                      <th>Strategy</th>
                      <th>Status</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(reportData?.trades || [])
                      .filter((t: any) => t.symbol.toLowerCase().includes(searchQuery.toLowerCase()))
                      .filter((t: any) => strategyFilter === 'All' || t.strategy === strategyFilter)
                      .map((trade: any) => (
                        <tr key={trade.id} style={{ background: trade.status === 'Win' ? 'rgba(16, 185, 129, 0.04)' : trade.status === 'Loss' ? 'rgba(239, 68, 68, 0.04)' : 'none' }}>
                          <td><strong>{trade.symbol}</strong></td>
                          <td><span className={`side-badge ${trade.side === 'BUY' ? 'long' : 'short'}`}>{trade.side}</span></td>
                          <td>{trade.qty}</td>
                          <td>₹{trade.entry_price?.toLocaleString()}</td>
                          <td>{trade.exit_price ? `₹${trade.exit_price.toLocaleString()}` : '-'}</td>
                          <td className={trade.pnl >= 0 ? 'positive' : 'negative'}>
                            {trade.pnl >= 0 ? '+' : ''}{trade.pnl?.toFixed(2)}
                          </td>
                          <td><span className="strategy-tag">{trade.strategy}</span></td>
                          <td>
                            <span className={`status-tag ${trade.status.toLowerCase()}`}>{trade.status}</span>
                          </td>
                          <td>{trade.time}</td>
                        </tr>
                    ))}
                    {(reportData?.trades?.length === 0) && (
                      <tr><td colSpan={9} style={{ textAlign: 'center', padding: '40px', opacity: 0.5 }}>No trades executed on this date.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Bottom Grid: Strategy & AI Insights */}
            <div className="report-bottom-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginTop: '32px' }}>
              <div className="strategy-card glass" style={{ padding: '20px', borderRadius: '12px' }}>
                <h3><LucidePieChart size={18} /> Strategy Performance</h3>
                <div className="strategy-list" style={{ marginTop: '16px' }}>
                  {reportData?.strategy_performance?.map((s: any) => (
                    <div key={s.name} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--border-color)' }}>
                      <div>
                        <strong>{s.name}</strong>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{s.trades} trades | {s.win_rate}% Win Rate</div>
                      </div>
                      <strong className={s.pnl >= 0 ? 'positive' : 'negative'}>
                        {s.pnl >= 0 ? '+' : ''}{formatCurrency(s.pnl)}
                      </strong>
                    </div>
                  ))}
                </div>
              </div>

              <div className="ai-insights-card glass highlight-ai" style={{ padding: '20px', borderRadius: '12px', border: '1px solid var(--accent-color)' }}>
                <h3 style={{ color: 'var(--accent-color)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <LucideActivity size={18} /> Institutional Insights
                </h3>
                <div className="insight-content" style={{ marginTop: '16px' }}>
                  <p style={{ fontSize: '14px', lineHeight: '1.6' }}>
                    {(reportData?.summary?.win_rate || 0) > 60 
                      ? "Excellent precision today. The High Conviction signals performed above expectations." 
                      : "Market volatility impacted lower-timeframe strategies. Consider tightening SL thresholds tomorrow."}
                  </p>
                  <ul style={{ paddingLeft: '20px', fontSize: '13px', color: 'var(--text-muted)' }}>
                    <li>Best Performer: {reportData?.strategy_performance?.[0]?.name || 'N/A'}</li>
                    <li>Avg Holding Quality: High</li>
                    <li>Risk Management Score: 92/100</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

const abs = (val: number) => Math.abs(val);

export default PaperPortfolio;
