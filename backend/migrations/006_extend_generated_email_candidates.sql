-- Migration: 006_extend_generated_email_candidates.sql
-- Description: Extend generated_email_candidates table with verification metadata, pattern_score, final_score, and rank position.

ALTER TABLE generated_email_candidates
ADD COLUMN IF NOT EXISTS pattern_score FLOAT,
ADD COLUMN IF NOT EXISTS final_score FLOAT,
ADD COLUMN IF NOT EXISTS rank INTEGER,
ADD COLUMN IF NOT EXISTS verification_status VARCHAR(50),
ADD COLUMN IF NOT EXISTS verification_confidence FLOAT,
ADD COLUMN IF NOT EXISTS verification_provider VARCHAR(50),
ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS is_disposable BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS is_role_account BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS is_catch_all BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS mx_checked BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS smtp_checked BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS verification_error TEXT;
