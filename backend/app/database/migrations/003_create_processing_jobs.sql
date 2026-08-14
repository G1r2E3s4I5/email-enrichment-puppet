-- Migration: 003_create_processing_jobs.sql
-- Purpose: Track CSV bulk processing jobs and job execution metadata

CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT NOT NULL DEFAULT 'UPLOADED',
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    total_rows INTEGER DEFAULT 0,
    processed_rows INTEGER DEFAULT 0,
    successful_rows INTEGER DEFAULT 0,
    failed_rows INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    queued_at TIMESTAMPTZ,

    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Performance & Status Query Indexes
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs (status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_created_at_desc ON processing_jobs (created_at DESC);

-- Disable Row Level Security for full API persistence access
ALTER TABLE processing_jobs DISABLE ROW LEVEL SECURITY;

