import React, { useEffect, useRef } from 'react';
import { CandlestickSeries, ColorType, createChart, IChartApi } from 'lightweight-charts';
import { HistoryPoint } from '../types/market';

interface TradingViewChartProps {
  data: HistoryPoint[];
  symbol: string;
  title: string;
  subtitle: string;
  rangeLabel: string;
}

const TradingViewChart: React.FC<TradingViewChartProps> = ({ data, symbol, title, subtitle, rangeLabel }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const hasData = Array.isArray(data) && data.length > 0;

  useEffect(() => {
    if (!chartContainerRef.current) return undefined;
    if (!hasData) {
      chartContainerRef.current.innerHTML = '';
      return undefined;
    }

    let chart: IChartApi | undefined;

    try {
      chartContainerRef.current.innerHTML = '';
      
      // SANITIZE DATA: Ensure unique timestamps and strictly ascending order
      const sanitizedData = [...data]
        .filter(d => d && typeof d.time === 'number' && !isNaN(d.close))
        .map(d => {
          const time = d.time > 10000000000 ? Math.floor(d.time / 1000) : d.time;
          // Apply IST Offset (+5:30) for visual display consistency with Indian markets
          return { ...d, time: time + (5.5 * 3600) };
        })
        .sort((a, b) => (a.time as number) - (b.time as number))
        .filter((item, index, self) => 
          index === 0 || (item.time as number) > (self[index - 1].time as number)
        );

      if (sanitizedData.length === 0) {
        chartContainerRef.current.innerHTML = '<div style="display:grid;place-items:center;min-height:420px;color:var(--text-secondary);">No valid chart data available.</div>';
        return undefined;
      }

      chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth || 600,
        height: 420,
        layout: {
          background: { type: ColorType.Solid, color: 'transparent' },
          textColor: '#6b7280',
          fontFamily: "'Outfit', sans-serif",
        },
        localization: {
          locale: 'en-IN',
          priceFormatter: (priceValue: number) => `₹${priceValue.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
          timeFormatter: (time: number) => {
             const date = new Date(time * 1000);
             const hours = date.getUTCHours().toString().padStart(2, '0');
             const minutes = date.getUTCMinutes().toString().padStart(2, '0');
             return `${hours}:${minutes}`;
          }
        },
        grid: {
          vertLines: { color: 'rgba(148, 163, 184, 0.12)' },
          horzLines: { color: 'rgba(148, 163, 184, 0.12)' },
        },
        rightPriceScale: {
          borderColor: 'rgba(148, 163, 184, 0.18)',
        },
        timeScale: {
          borderColor: 'rgba(148, 163, 184, 0.18)',
          timeVisible: true,
          secondsVisible: false,
          shiftVisibleRangeOnNewBar: true,
        },
        crosshair: {
          vertLine: { color: 'rgba(99, 102, 241, 0.35)' },
          horzLine: { color: 'rgba(99, 102, 241, 0.35)' },
        },
      });

      const series = chart.addSeries(CandlestickSeries, {
        upColor: '#16a34a',
        downColor: '#dc2626',
        wickUpColor: '#16a34a',
        wickDownColor: '#dc2626',
        borderUpColor: '#16a34a',
        borderDownColor: '#dc2626',
      });

      series.setData(sanitizedData as any);
      chart.timeScale().fitContent();
    } catch (error) {
      console.error('TradingViewChart failed to initialize:', error);
      if (chartContainerRef.current) {
        chartContainerRef.current.innerHTML =
          '<div style="display:grid;place-items:center;min-height:420px;color:var(--text-secondary);">Chart renderer failed to initialize.</div>';
      }
      return undefined;
    }

    const handleResize = () => {
      if (!chartContainerRef.current || !chart) return;
      chart.applyOptions({ width: chartContainerRef.current.clientWidth || 600 });
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chart) {
        chart.remove();
      }
    };
  }, [data, hasData, rangeLabel]);

  const latest = hasData ? data[data.length - 1] : { close: 0 };
  const previous = hasData ? data[data.length - 2] ?? latest : latest;
  const delta = (latest.close ?? 0) - (previous.close ?? 0);
  const change = previous.close ? (delta / previous.close) * 100 : 0;

  return (
    <div className="tv-shell">
      <div className="tv-header">
        <div>
          <span className="panel-kicker">TradingView-style feed</span>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        <div className="tv-stats">
          <span>{symbol}</span>
          <strong>{latest.close?.toLocaleString('en-IN') ?? '-'}</strong>
          <small className={change >= 0 ? 'positive' : 'negative'}>
            {change >= 0 ? '+' : ''}{change.toFixed(2)}% ({rangeLabel})
          </small>
        </div>
      </div>
      {!hasData ? (
        <div className="tv-chart glass" style={{ display: 'grid', placeItems: 'center', minHeight: '420px' }}>
          <div style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
            <strong style={{ display: 'block', marginBottom: '8px', color: 'var(--text-primary)' }}>
              Chart unavailable
            </strong>
            <span>No chart data available.</span>
          </div>
        </div>
      ) : (
        <div className="tv-chart" ref={chartContainerRef} />
      )}
    </div>
  );
};

export default TradingViewChart;
