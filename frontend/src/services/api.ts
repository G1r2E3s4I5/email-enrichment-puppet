import {
  ServiceStatus,
  HealthStatus,
  JobUploadResponse,
  QueueJobResponse,
  JobDetailResponse,
  JobListResponse,
  JobStatisticsResponse,
  DashboardOverview,
  JobAnalytics,
  WorkerAnalytics,
  ProviderAnalytics,
  CacheAnalytics,
  VerificationAnalytics,
  PerformanceAnalytics,
  ExportFormat,
  ExportFilter,
} from '../types';

/**
 * Get configured FastAPI backend base URL.
 * Prefers VITE_API_URL / VITE_API_BASE_URL, then localStorage setting, fallback to http://127.0.0.1:8000.
 */
const getBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL;
  if (envUrl && envUrl.trim() !== '' && envUrl !== '/api') {
    return envUrl.replace(/\/$/, '');
  }

  if (typeof window !== 'undefined') {
    const savedUrl = localStorage.getItem('settings_api_url');
    if (savedUrl && savedUrl.trim() !== '' && savedUrl !== '/api') {
      return savedUrl.replace(/\/$/, '');
    }
  }

  return 'http://127.0.0.1:8000';
};

/**
 * Service API wrapper for Email Enrichment backend interaction.
 */
export const ApiService = {
  /**
   * Fetch root service status.
   */
  async getServiceStatus(): Promise<ServiceStatus> {
    const baseUrl = getBaseUrl();
    try {
      const response = await fetch(`${baseUrl}/`);
      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch service status:', error);
      return { service: 'Email Enrichment Tool', status: 'disconnected' };
    }
  },

  /**
   * Fetch system health status.
   */
  async getHealthStatus(): Promise<HealthStatus> {
    const baseUrl = getBaseUrl();
    try {
      const response = await fetch(`${baseUrl}/api/health`);
      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Failed to fetch health status:', error);
      return { status: 'unreachable' };
    }
  },

  /**
   * Upload CSV file for bulk email enrichment job initialization.
   */
  async uploadCSV(file: File): Promise<JobUploadResponse> {
    const baseUrl = getBaseUrl();
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${baseUrl}/api/v1/jobs/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to upload CSV file' }));
      throw new Error(errorData.detail || `Upload failed with HTTP ${response.status}`);
    }

    return await response.json();
  },

  /**
   * Queue validated processing job to Redis queue for background worker execution.
   */
  async queueJob(jobId: string): Promise<QueueJobResponse> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/jobs/${jobId}/queue`, {
      method: 'POST',
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to queue job' }));
      throw new Error(errorData.detail || `Failed to queue job ${jobId}`);
    }

    return await response.json();
  },

  /**
   * Fetch processing job detail by ID.
   */
  async getJobDetail(jobId: string): Promise<JobDetailResponse> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/jobs/${jobId}`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Job not found' }));
      throw new Error(errorData.detail || `Failed to fetch job ${jobId}`);
    }
    return await response.json();
  },

  /**
   * Fetch list of jobs with pagination and status filters.
   */
  async getJobsList(status?: string, limit: number = 50, offset: number = 0): Promise<JobListResponse> {
    const baseUrl = getBaseUrl();
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    if (status && status !== 'all') {
      params.append('status', status);
    }

    const response = await fetch(`${baseUrl}/api/v1/jobs?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch jobs list: HTTP ${response.status}`);
    }
    return await response.json();
  },

  /**
   * Fetch detailed job statistics by job ID.
   */
  async getJobStatistics(jobId: string): Promise<JobStatisticsResponse> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/jobs/${jobId}/statistics`);
    if (!response.ok) {
      throw new Error(`Failed to fetch job statistics for ${jobId}`);
    }
    return await response.json();
  },

  /**
   * Cancel/stop processing for a specific job.
   */
  async stopJob(jobId: string): Promise<JobDetailResponse> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/jobs/${jobId}/stop`, {
      method: 'POST',
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Failed to stop job' }));
      throw new Error(errorData.detail || `Failed to stop job ${jobId}`);
    }
    return await response.json();
  },

  /**
   * Stop background worker engine gracefully.
   */
  async stopWorker(): Promise<any> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/workers/stop`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(`Failed to stop background worker`);
    }
    return await response.json();
  },

  /**
   * Start background worker engine loop.
   */
  async startWorker(): Promise<any> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/workers/start`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(`Failed to start background worker`);
    }
    return await response.json();
  },

  /**
   * Build export download URL.
   */
  getExportUrl(jobId: string, format: ExportFormat = 'csv', filter: ExportFilter = 'full', stream: boolean = false): string {
    const baseUrl = getBaseUrl();
    return `${baseUrl}/api/v1/jobs/${jobId}/export?format=${format}&filter=${filter}&stream=${stream}`;
  },

  /**
   * Fetch dashboard overview.
   */
  async getDashboardOverview(): Promise<DashboardOverview> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/dashboard/overview`);
    if (!response.ok) {
      throw new Error(`Failed to fetch dashboard overview`);
    }
    return await response.json();
  },

  /**
   * Fetch job analytics.
   */
  async getJobAnalytics(): Promise<JobAnalytics> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/analytics/jobs`);
    if (!response.ok) throw new Error('Failed to fetch job analytics');
    return await response.json();
  },

  /**
   * Fetch worker analytics.
   */
  async getWorkerAnalytics(): Promise<WorkerAnalytics> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/analytics/workers`);
    if (!response.ok) throw new Error('Failed to fetch worker analytics');
    return await response.json();
  },

  /**
   * Fetch provider analytics.
   */
  async getProviderAnalytics(): Promise<ProviderAnalytics> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/analytics/providers`);
    if (!response.ok) throw new Error('Failed to fetch provider analytics');
    return await response.json();
  },

  /**
   * Fetch cache analytics.
   */
  async getCacheAnalytics(): Promise<CacheAnalytics> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/analytics/cache`);
    if (!response.ok) throw new Error('Failed to fetch cache analytics');
    return await response.json();
  },

  /**
   * Fetch verification analytics.
   */
  async getVerificationAnalytics(): Promise<VerificationAnalytics> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/analytics/verification`);
    if (!response.ok) throw new Error('Failed to fetch verification analytics');
    return await response.json();
  },

  /**
   * Fetch performance analytics.
   */
  async getPerformanceAnalytics(): Promise<PerformanceAnalytics> {
    const baseUrl = getBaseUrl();
    const response = await fetch(`${baseUrl}/api/v1/analytics/performance`);
    if (!response.ok) throw new Error('Failed to fetch performance analytics');
    return await response.json();
  },
};
