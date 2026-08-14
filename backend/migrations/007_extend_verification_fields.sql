-- Migration: 007_extend_verification_fields.sql
-- Description: Extend generated_email_candidates table with detailed MX, SMTP, duration, and method verification metadata.

ALTER TABLE generated_email_candidates
ADD COLUMN IF NOT EXISTS mx_exists BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS mx_records TEXT,
ADD COLUMN IF NOT EXISTS smtp_status VARCHAR(50),
ADD COLUMN IF NOT EXISTS smtp_code INTEGER,
ADD COLUMN IF NOT EXISTS smtp_message TEXT,
ADD COLUMN IF NOT EXISTS verification_method VARCHAR(50),
ADD COLUMN IF NOT EXISTS verification_duration_ms FLOAT DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS verification_completed_at TIMESTAMPTZ;
