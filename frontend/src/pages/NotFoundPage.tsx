import React from 'react';
import { Link } from 'react-router-dom';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
      <h1 style={{ fontSize: '3rem', fontWeight: 800, color: 'var(--accent-primary)' }}>404</h1>
      <h2 style={{ fontSize: '1.5rem', fontWeight: 600, marginTop: '0.5rem' }}>Page Not Found</h2>
      <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem', marginBottom: '1.5rem' }}>
        The page you are looking for does not exist in the Email Enrichment Tool portal.
      </p>
      <Link
        to="/"
        style={{
          display: 'inline-block',
          background: 'var(--accent-primary)',
          color: '#ffffff',
          padding: '0.75rem 1.5rem',
          borderRadius: '8px',
          fontWeight: 600,
        }}
      >
        Return to Dashboard
      </Link>
    </div>
  );
};
