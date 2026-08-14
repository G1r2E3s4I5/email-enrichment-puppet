-- Migration: 002_create_domain_resolution_logs.sql
-- Purpose: Audit log table to record every domain lookup attempt and provider response

CREATE TABLE IF NOT EXISTS domain_resolution_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT,
    normalized_name TEXT,
    resolved_domain TEXT,
    provider TEXT,
    cached BOOLEAN DEFAULT FALSE,
    response_time_ms INTEGER,
    status TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance & Query Audit Indexes
CREATE INDEX IF NOT EXISTS idx_domain_logs_company_name ON domain_resolution_logs (company_name);
CREATE INDEX IF NOT EXISTS idx_domain_logs_created_at_desc ON domain_resolution_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_domain_logs_status ON domain_resolution_logs (status);
