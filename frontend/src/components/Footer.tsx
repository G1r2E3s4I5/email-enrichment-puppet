import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="footer">
      <p>
        Email Enrichment Tool &copy; {new Date().getFullYear()} — Architecture & Infrastructure Foundation (Phase 0.5)
      </p>
    </footer>
  );
};
