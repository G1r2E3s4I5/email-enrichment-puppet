import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navigation } from '../components/Navigation';

export const MainLayout: React.FC = () => {
  return (
    <div className="app-container">
      <Navigation />
      <main className="main-content">
        <Outlet />
      </main>
      <footer className="footer">
        <p>Email Enrichment Platform &copy; 2026 — Parallel Domain Resolution & High-Throughput Verification Engine</p>
      </footer>
    </div>
  );
};
