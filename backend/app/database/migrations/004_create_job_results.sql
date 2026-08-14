-- Migration: 004_create_job_results.sql
-- Purpose: Store per-row company domain resolution results for bulk jobs

CREATE TABLE IF NOT EXISTS job_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    company TEXT NOT NULL,
    resolved_domain TEXT,
    provider TEXT,
    cached BOOLEAN DEFAULT FALSE,
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_job_results_job_id ON job_results (job_id);
CREATE INDEX IF NOT EXISTS idx_job_results_row_number ON job_results (job_id, row_number);

-- Disable Row Level Security for full API persistence access
ALTER TABLE job_results DISABLE ROW LEVEL SECURITY;

