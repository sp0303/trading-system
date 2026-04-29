import React, { useMemo, useState } from 'react';
import { 
  ArrowUpRight, 
  ArrowDownRight, 
  Filter, 
  Clock,
  Zap
} from 'lucide-react';
import SignalCard from './SignalCard';
import { Signal } from '../types/market';

interface SignalsGalleryProps {
  signals: Signal[];
  loading: boolean;
  onSelect: (symbol: string) => void;
  selectedSymbol: string;
}

const SignalsGallery: React.FC<SignalsGalleryProps> = ({ signals, loading, onSelect, selectedSymbol }) => {
  const [filterStrategy, setFilterStrategy] = useState('All');
  
  const strategies = useMemo(() => {
    const set = new Set(signals.map(s => s.strategy));
    return ['All', ...Array.from(set)];
  }, [signals]);

  const filteredSignals = useMemo(() => {
    let filtered = [...signals];
    
    if (filterStrategy !== 'All') {
      filtered = filtered.filter(s => s.strategy === filterStrategy);
    }
    
    // Sort by Win Probability descending
    return filtered.sort((a, b) => (b.probability || 0) - (a.probability || 0));
  }, [signals, filterStrategy]);

  const stats = useMemo(() => {
    const longs = signals.filter(s => s.direction === 'BUY' || s.direction === 'BULLISH').length;
    const shorts = signals.filter(s => s.direction === 'SELL' || s.direction === 'BEARISH' || s.direction === 'SHORT' as any).length;
    const highProb = signals.filter(s => s.probability > 0.7).length;
    
    return { longs, shorts, highProb };
  }, [signals]);

  return (
    <div className="signals-gallery fade-in" id="signals-gallery">
      <header className="gallery-header">
        <div className="gallery-title">
          <div className="eyebrow">Execution Console</div>
          <h2>Live Signal Control Room</h2>
          <p>Institutional ensemble triggers across the Nifty 500 universe, ordered by predictive conviction.</p>
        </div>
        
        <div className="gallery-stats">
          <div className="mini-stat">
            <span className="label">Longs</span>
            <span className="value positive"><ArrowUpRight size={14}/> {stats.longs}</span>
          </div>
          <div className="mini-stat">
            <span className="label">Shorts</span>
            <span className="value negative"><ArrowDownRight size={14}/> {stats.shorts}</span>
          </div>
          <div className="mini-stat">
            <span className="label">High Conviction</span>
            <span className="value primary"><Zap size={14}/> {stats.highProb}</span>
          </div>
        </div>
      </header>

      <div className="gallery-toolbar glass shadow-sm">
        <div className="filter-group">
          <Filter size={16} />
          <div className="pill-group">
            {strategies.map(strat => (
              <button 
                key={strat}
                className={`pill ${filterStrategy === strat ? 'active' : ''}`}
                onClick={() => setFilterStrategy(strat)}
              >
                {strat}
              </button>
            ))}
          </div>
        </div>
        <div className="timestamp-info">
          <Clock size={16} />
          <span>Last updated: {new Date().toLocaleTimeString()}</span>
        </div>
      </div>

      <div className="signals-grid">
        {loading ? (
          <div className="empty-state large glass">
            <div className="spinner"></div>
            <p>Gathering signals from the ensemble backend...</p>
          </div>
        ) : filteredSignals.length === 0 ? (
          <div className="empty-state large glass">
            <Zap size={48} className="muted" />
            <p>No active {filterStrategy !== 'All' ? filterStrategy : ''} signals match your institutional filters.</p>
          </div>
        ) : (
          filteredSignals.map((signal, index) => (
            <div key={`${signal.symbol}-${index}`} className="gallery-item scale-in">
              <SignalCard 
                signal={signal} 
                selected={signal.symbol === selectedSymbol}
                onSelect={onSelect}
              />
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default SignalsGallery;
