/**
 * Comprehensive TypeScript interfaces for Email Enrichment Platform.
 */

export interface ServiceStatus {
  service: string;
  status: string;
}

export interface HealthStatus {
  status: string;
  database?: {
    status: string;
    connected: boolean;
    message: string;
  };
}

export interface APIResponseEnvelope<T> {
  success: boolean;
  message: string;
  data: T | null;
  error: {
    code: string;
    message: string;
    details: unknown;
  } | null;
}

export interface JobUploadResponse {
  job_id: string;
  status: string;
  original_filename: string;
  stored_filename: string;
  file_size: number;
  rows: number;
  headers: string[];
  preview: Record<string, string>[];
  warnings: string[];
}

export interface QueueJobResponse {
  success: boolean;
  job_id: string;
  status: string;
  queue_position: number;
}

export interface JobSummary {
  job_id: string;
  original_filename: string;
  status: 'draft' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'UPLOADED' | 'VALIDATED';
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  row_count: number;
  processed_rows: number;
  successful_rows: number;
  failed_rows: number;
  duration_sec?: number;
  progress_percentage: number;
  error_message?: string;
}

export interface JobListResponse {
  total_count: number;
  limit: number;
  offset: number;
  jobs: JobSummary[];
}

export interface JobDetailResponse {
  id: string;
  status: string;
  original_filename: string;
  stored_filename: string;
  file_size: number;
  total_rows: number;
  processed_rows: number;
  successful_rows: number;
  failed_rows: number;
  created_at?: string;
  updated_at?: string;
  queued_at?: string;
  started_at?: string;
  completed_at?: string;
  duration_sec?: number;
  error_message?: string;
  metadata?: Record<string, unknown>;
}

export interface JobResultRecord {
  id: string;
  job_id: string;
  row_number: number;
  company: string;
  resolved_domain?: string;
  provider?: string;
  cached: boolean;
  success: boolean;
  processed_at?: string;
  error_message?: string;
}

export interface GeneratedCandidateRecord {
  id: string;
  job_id: string;
  row_number: number;
  candidate_email: string;
  pattern_name: string;
  rank?: number;
  confidence_score?: number;
  final_score?: number;
  pattern_score?: number;
  verification_status?: string;
  verification_confidence?: number;
  verification_provider?: string;
  mx_checked?: boolean;
  smtp_checked?: boolean;
  is_disposable?: boolean;
  is_role_account?: boolean;
  is_catch_all?: boolean;
  created_at?: string;
}

export interface JobStatisticsResponse {
  job_id: string;
  status: string;
  original_filename: string;
  created_at?: string;
  completed_at?: string;
  duration_sec?: number;
  row_count: number;
  processed_rows: number;
  successful_rows: number;
  failed_rows: number;
  companies_resolved?: number;
  cache_hit_count: number;
  cache_hit_rate: number;
  cache_hit_rate_percentage?: number;
  verification_success_rate: number;
  success_rate_percentage?: number;
  average_confidence: number;
  average_ranking_score?: number;
  total_candidates_generated: number;
  candidates_generated_total?: number;
  provider_usage?: Record<string, number>;
  provider_breakdown?: Record<string, number>;
  processing_speed_rows_per_sec?: number;
}

export interface JobAnalytics {
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  processing_jobs: number;
  total_companies_processed: number;
  successful_enrichment_rows: number;
  overall_success_rate_pct: number;
}

export interface WorkerAnalytics {
  total_active_workers: number;
  active_worker_ids: string[];
  worker_status: string;
  concurrency_limit_per_worker: number;
}

export interface ProviderTelemetry {
  name?: string;
  status: string;
  healthy: boolean;
  consecutive_failures?: number;
  consecutive_successes?: number;
  cooldown_remaining_sec?: number;
  total_requests?: number;
  successful_requests?: number;
  failed_requests?: number;
  rate_limit_429_count?: number;
  success_rate_pct?: number;
  average_latency_ms?: number;
}

export interface ProviderAnalytics {
  primary_provider: string;
  fallback_provider: string;
  brandfetch: ProviderTelemetry;
  serpapi: ProviderTelemetry;
}

export interface CacheAnalytics {
  cached_domains_total: number;
  negative_lookups_cached: number;
  cache_hit_rate_pct: number;
  cache_hit_rate?: number;
}

export interface VerificationAnalytics {
  active_verification_provider: string;
  verification_success_rate_pct: number;
  verified_valid_pct: number;
  verified_catch_all_pct: number;
  disposable_rejected_count: number;
  role_account_flagged_count: number;
}

export interface PerformanceAnalytics {
  average_rows_per_second: number;
  average_emails_per_second: number;
  average_confidence_score: number;
  average_job_duration_sec: number;
  top_email_patterns: string[];
}

export interface DashboardOverview {
  jobs_summary: JobAnalytics;
  workers_summary: WorkerAnalytics;
  providers_summary: ProviderAnalytics;
  cache_summary: CacheAnalytics;
  verification_summary: VerificationAnalytics;
  performance_summary: PerformanceAnalytics;
}

export type ExportFormat = 'csv' | 'xlsx' | 'json';
export type ExportFilter = 'full' | 'top_ranked_only' | 'successful_only' | 'failed_only';

export interface UserAuth {
  isAuthenticated: boolean;
  user: {
    email: string;
    name: string;
    role: string;
  } | null;
}
