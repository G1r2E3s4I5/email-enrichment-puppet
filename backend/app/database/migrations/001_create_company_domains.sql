-- Migration: 001_create_company_domains.sql
-- Purpose: Cache company to domain mappings for rapid resolution lookups

CREATE TABLE IF NOT EXISTS company_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    provider TEXT NOT NULL,
    confidence DOUBLE PRECISION DEFAULT 1.0,
    preferred_pattern TEXT,
    pattern_confidence DOUBLE PRECISION DEFAULT 0.0,
    pattern_last_verified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_company_domains_normalized_name ON company_domains (normalized_name);
CREATE INDEX IF NOT EXISTS idx_company_domains_domain ON company_domains (domain);
