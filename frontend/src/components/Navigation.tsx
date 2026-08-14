import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  UploadCloud,
  ListFilter,
  BarChart3,
  Cpu,
  Settings,
  Mail,
} from 'lucide-react';
import { ApiService } from '../services/api';

export const Navigation: React.FC = () => {
  const [healthStatus, setHealthStatus] = useState<string>('checking');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await ApiService.getHealthStatus();
        setHealthStatus(res.status === 'healthy' ? 'online' : 'degraded');
      } catch {
        setHealthStatus('offline');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="header">
      <div className="header-brand-container">
        <Mail className="brand-logo" size={24} />
        <span className="header-brand">Email Enrichment Platform</span>
        <div className={`health-indicator health-${healthStatus}`} title={`System Status: ${healthStatus}`}>
          <span className="health-dot"></span>
          <span className="health-text">{healthStatus}</span>
        </div>
      </div>

      <nav className="header-nav">
        <NavLink to="/dashboard" className={({ isActive }) => `header-link ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>
        <NavLink to="/upload" className={({ isActive }) => `header-link ${isActive ? 'active' : ''}`}>
          <UploadCloud size={18} />
          <span>Upload CSV</span>
        </NavLink>
        <NavLink to="/jobs" className={({ isActive }) => `header-link ${isActive ? 'active' : ''}`}>
          <ListFilter size={18} />
          <span>Jobs</span>
        </NavLink>
        <NavLink to="/analytics" className={({ isActive }) => `header-link ${isActive ? 'active' : ''}`}>
          <BarChart3 size={18} />
          <span>Analytics</span>
        </NavLink>
        <NavLink to="/workers" className={({ isActive }) => `header-link ${isActive ? 'active' : ''}`}>
          <Cpu size={18} />
          <span>Workers</span>
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => `header-link ${isActive ? 'active' : ''}`}>
          <Settings size={18} />
          <span>Settings</span>
        </NavLink>
      </nav>
    </header>
  );
};
