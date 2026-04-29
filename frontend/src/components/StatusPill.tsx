import React, { useEffect, useState } from 'react';
import { LucideActivity } from 'lucide-react';

interface StatusPillProps {
  lastUpdated: Date | null;
  isRefreshing?: boolean;
  label?: string;
}

const StatusPill: React.FC<StatusPillProps> = ({ lastUpdated, isRefreshing = false, label = 'Live Monitoring' }) => {
  const [secondsAgo, setSecondsAgo] = useState<number>(0);

  useEffect(() => {
    if (!lastUpdated) return;

    const updateSeconds = () => {
      const now = new Date();
      const diff = Math.floor((now.getTime() - lastUpdated.getTime()) / 1000);
      setSecondsAgo(Math.max(0, diff));
    };

    updateSeconds();
    const interval = setInterval(updateSeconds, 1000);
    return () => clearInterval(interval);
  }, [lastUpdated]);

  const getTimeText = () => {
    if (!lastUpdated) return 'Connecting...';
    if (secondsAgo < 5) return 'Just now';
    return `${secondsAgo}s ago`;
  };

  return (
    <div className={`status-pill-container ${isRefreshing ? 'refreshing' : ''}`}>
      <div className="pulse-dot-wrapper">
        <div className="pulse-dot"></div>
        <div className="pulse-ring"></div>
      </div>
      <div className="status-text-group">
        <span className="status-label">{label}</span>
        <span className="status-time">{getTimeText()}</span>
      </div>
      {isRefreshing && (
        <div className="refresh-mini-icon">
           <LucideActivity size={10} className="spin-slow" />
        </div>
      )}
    </div>
  );
};

export default StatusPill;
