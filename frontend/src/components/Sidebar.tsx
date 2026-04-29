import React from 'react';
import { 
  LayoutDashboard, 
  Activity, 
  BarChart2, 
  Settings, 
  ShieldCheck, 
  Bell,
  LucideIcon,
  X
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import './Sidebar.css';

interface MenuItem {
  id: string;
  icon: LucideIcon;
  label: string;
  badge?: number;
}

interface SidebarProps {
  activeTab: string;
  onTabChange: (id: string) => void;
  signalCount: number;
  isOpen?: boolean;
  onClose?: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange, signalCount, isOpen, onClose }) => {
  const menuItems: MenuItem[] = [
    { id: 'Dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { id: 'Portfolio', icon: BarChart2, label: 'Paper Portfolio' },
    { id: 'Signals', icon: Activity, label: 'Active Signals', badge: signalCount },
    { id: 'Alerts', icon: Bell, label: 'Alerts' },
    { id: 'Logs', icon: ShieldCheck, label: 'Logs' },
    { id: 'Settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <>
      <div 
        className={`sidebar-backdrop ${isOpen ? 'visible' : ''}`} 
        onClick={onClose}
      />
      <aside className={`sidebar ${isOpen ? 'open' : ''}`}>
        <div className="sidebar-logo-section">
          <div className="sidebar-logo-icon">
            <Activity size={20} />
          </div>
          <h2 className="sidebar-logo-text">
            Nifty 500 <span style={{ color: 'var(--accent-color)' }}>Elite</span>
          </h2>
          {isOpen && onClose && (
          <button 
            onClick={onClose}
            className="sidebar-close-btn mobile-only"
          >
            <X size={20} />
          </button>

          )}
        </div>

        <nav className="sidebar-nav">
          <ul className="sidebar-menu">
            {menuItems.map((item) => {
              const isActive = activeTab === item.id;
              return (
                <li key={item.id}>
                  <button 
                    onClick={() => {
                      onTabChange(item.id);
                      if (onClose) onClose();
                    }}
                    className={`sidebar-btn glass-hover ${isActive ? 'active' : ''}`}
                  >
                    <item.icon size={18} />
                    <span style={{ flex: 1, textAlign: 'left' }}>{item.label}</span>
                    {item.badge != null && item.badge > 0 && (
                      <span className="sidebar-badge">
                        {item.badge}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar">
              JD
            </div>
            <div className="user-info">
              <span className="user-name">Trader Joe</span>
              <span className="user-type">Pro Account</span>
            </div>
          </div>
          <ThemeToggle />
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
