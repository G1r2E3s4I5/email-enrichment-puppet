-- Migration: 005_create_generated_email_candidates.sql
-- Purpose: Store generated candidate email permutations per row for bulk jobs

CREATE TABLE IF NOT EXISTS generated_email_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    candidate_email TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_generated_email_candidates_job_id ON generated_email_candidates (job_id);
CREATE INDEX IF NOT EXISTS idx_generated_email_candidates_row ON generated_email_candidates (job_id, row_number);

-- Disable Row Level Security for full API access
ALTER TABLE generated_email_candidates DISABLE ROW LEVEL SECURITY;
