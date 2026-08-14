import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export const Header: React.FC = () => {
  const location = useLocation();

  return (
    <header className="header">
      <div className="header-brand">
        <Link to="/">Email Enrichment Tool</Link>
      </div>
      <nav className="header-nav">
        <Link
          to="/"
          className={`header-link ${location.pathname === '/' ? 'active' : ''}`}
        >
          Dashboard
        </Link>
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="header-link"
        >
          Swagger Docs
        </a>
      </nav>
    </header>
  );
};
