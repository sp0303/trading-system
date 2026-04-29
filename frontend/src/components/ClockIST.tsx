import React, { useState, useEffect } from 'react';

const ClockIST: React.FC = () => {
  const [time, setTime] = useState<Date>(new Date());

  useEffect(() => {
    // Update the clock every 100ms so the milliseconds field runs relatively smoothly
    const interval = setInterval(() => {
      setTime(new Date());
    }, 100);
    return () => clearInterval(interval);
  }, []);

  // Format as IST
  const opts: Intl.DateTimeFormatOptions = { 
    timeZone: 'Asia/Kolkata', 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit',
    hour12: true
  };
  
  const formattedTime = new Intl.DateTimeFormat('en-IN', opts).format(time);
  
  // Extract milliseconds
  const ms = time.getMilliseconds().toString().padStart(3, '0');

  // Format Date (e.g., 24 Oct 2024)
  const dateOpts: Intl.DateTimeFormatOptions = {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  };
  const formattedDate = new Intl.DateTimeFormat('en-IN', dateOpts).format(time);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', justifyContent: 'center' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
        <strong style={{ fontSize: '18px', fontFamily: '"JetBrains Mono", monospace' }}>
          {formattedTime}
        </strong>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: '"JetBrains Mono", monospace' }}>
          .{ms}
        </span>
      </div>
      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {formattedDate} • NSE/BSE (IST)
      </div>
    </div>
  );
};

export default ClockIST;
