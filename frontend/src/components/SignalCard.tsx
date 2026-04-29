import React from 'react';
import {
  Clock,
  Percent,
  Shield,
  Target,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { Signal } from '../types/market';

import { createPaperOrder } from '../api/market';

interface SignalCardProps {
  signal: Signal;
  onSelect?: (symbol: string) => void;
  selected?: boolean;
}

const SignalCard: React.FC<SignalCardProps> = ({ signal, onSelect, selected = false }) => {
  const [placing, setPlacing] = React.useState(false);
  const [qty, setQty] = React.useState(1);

  const {
    symbol,
    probability,
    confidence,
    direction,
    entry,
    stop_loss,
    target_l1,
    target_l2,
    target_l3,
    strategy,
    regime,
    timestamp,
  } = signal;

  const isBuy = direction === 'BUY' || direction === 'BULLISH';
  const tone = isBuy ? 'var(--success-color)' : 'var(--error-color)';
  const ts = new Date(timestamp);
  const timeString = ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const handlePaperTrade = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setPlacing(true);
    try {
      await createPaperOrder({
        symbol,
        side: isBuy ? 'BUY' : 'SHORT',
        qty: Math.max(1, qty), 
        requested_price: entry,
        strategy_name: strategy,
        regime,
        trade_signal_id: signal.id,
        source: 'frontend',
        extra: {
          stop_loss,
          target_l1,
          target_l2,
          target_l3,
          probability,
          confidence
        }
      });
      alert(`Paper trade placed: ${qty} units of ${symbol}`);
    } catch (err: any) {
      alert(`Failed to place paper trade: ${err.message}`);
    } finally {
      setPlacing(false);
    }
  };

  return (
    <button
      type="button"
      className={`glass signal-card ${selected ? 'selected' : ''}`}
      onClick={() => onSelect?.(symbol)}
    >
      <div className="signal-card-header">
        <div className="signal-card-symbol">
          <div className="signal-direction-icon" style={{ backgroundColor: `${tone}1A`, color: tone }}>
            {isBuy ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
          </div>
          <div>
            <strong>{symbol}</strong>
            <span>{direction} . {strategy}</span>
          </div>
        </div>
        <div className="signal-card-price">
          <span><Clock size={12} /> {timeString}</span>
          <strong>₹{Number(entry).toFixed(2)}</strong>
        </div>
      </div>

      <div className="signal-metrics">
        <div>
          <span><Percent size={12} /> Probability</span>
          <strong style={{ color: tone }}>{(probability * 100).toFixed(1)}%</strong>
        </div>
        <div>
          <span><Shield size={12} /> Confidence</span>
          <strong>{(confidence * 100).toFixed(1)}%</strong>
        </div>
        <div>
          <span><Target size={12} /> Regime</span>
          <strong>{regime}</strong>
        </div>
        <div className="paper-trade-action" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
           <input 
             type="number" 
             value={qty} 
             onChange={(e) => setQty(parseInt(e.target.value) || 1)}
             min="1"
             className="qty-input-small"
             onClick={(e) => e.stopPropagation()}
             style={{ width: '40px', fontSize: '10px', padding: '2px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'white', textAlign: 'center' }}
           />
           <button 
             className="paper-trade-btn" 
             onClick={handlePaperTrade}
             disabled={placing}
             style={{ 
               backgroundColor: `${tone}26`, 
               color: tone, 
               border: `1px solid ${tone}`,
               borderRadius: '4px',
               padding: '2px 8px',
               fontSize: '11px',
               fontWeight: 'bold',
               cursor: 'pointer'
             }}
           >
             {placing ? '...' : (isBuy ? 'Buy' : 'Short')}
           </button>
        </div>
      </div>

      <div className="signal-targets">
        <div>
          <span>Stop</span>
          <strong>₹{Number(stop_loss).toFixed(2)}</strong>
        </div>
        <div>
          <span>L2</span>
          <strong>₹{Number(target_l2).toFixed(2)}</strong>
        </div>
        <div>
          <span>L3</span>
          <strong>₹{Number(target_l3).toFixed(2)}</strong>
        </div>
      </div>

      <div className="signal-progress" style={{ marginTop: 'auto' }}>
        <div style={{ width: `${probability * 100}%`, backgroundColor: tone }} />
      </div>

    </button>
  );
};

export default SignalCard;
