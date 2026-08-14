import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Briefcase,
  CheckCircle,
  XCircle,
  Clock,
  Cpu,
  Zap,
  ShieldCheck,
  UploadCloud,
  ArrowRight,
  Database,
} from 'lucide-react';
import { ApiService } from '../services/api';
import { DashboardOverview, JobSummary } from '../types';
import { useToast } from '../components/Toast';

export const DashboardPage: React.FC = () => {
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [recentJobs, setRecentJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const { addToast } = useToast();

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [dashRes, jobsRes] = await Promise.all([
          ApiService.getDashboardOverview(),
          ApiService.getJobsList('all', 5, 0),
        ]);
        setOverview(dashRes);
        setRecentJobs(jobsRes.jobs || []);
      } catch (err) {
        console.error('Failed to load dashboard overview:', err);
        addToast('error', 'Dashboard Error', 'Failed to load live metrics from backend.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, []);

  const jobsSummary = overview?.jobs_summary;
  const workersSummary = overview?.workers_summary;
  const cacheSummary = overview?.cache_summary;
  const performanceSummary = overview?.performance_summary;
  const verificationSummary = overview?.verification_summary;

  const cacheHitRate = cacheSummary?.cache_hit_rate_pct ?? cacheSummary?.cache_hit_rate ?? 0;
  const throughputSpeed = performanceSummary?.average_rows_per_second ?? 0;
  const verificationRate = verificationSummary?.verification_success_rate_pct ?? 0;
  const activeWorkers = workersSummary?.total_active_workers ?? 0;

  return (
    <div className="dashboard-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Executive Dashboard</h1>
          <p className="page-subtitle">Real-time pipeline metrics, background queue depth & system performance</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}>
          <UploadCloud size={18} /> Upload New CSV
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="kpi-grid">
        <div className="kpi-card card">
          <div className="kpi-icon kpi-blue">
            <Briefcase size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Total Jobs</span>
            <span className="kpi-value">{loading ? '...' : (jobsSummary?.total_jobs ?? 0)}</span>
            <span className="kpi-subtext">Lifetime batch runs</span>
          </div>
        </div>

        <div className="kpi-card card">
          <div className="kpi-icon kpi-green">
            <CheckCircle size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Completed Jobs</span>
            <span className="kpi-value">{loading ? '...' : (jobsSummary?.completed_jobs ?? 0)}</span>
            <span className="kpi-subtext">Successful runs</span>
          </div>
        </div>

        <div className="kpi-card card">
          <div className="kpi-icon kpi-yellow">
            <Clock size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Active Queue</span>
            <span className="kpi-value">{loading ? '...' : (jobsSummary?.processing_jobs ?? 0)}</span>
            <span className="kpi-subtext">Queued / Processing</span>
          </div>
        </div>

        <div className="kpi-card card">
          <div className="kpi-icon kpi-red">
            <XCircle size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Failed Jobs</span>
            <span className="kpi-value">{loading ? '...' : (jobsSummary?.failed_jobs ?? 0)}</span>
            <span className="kpi-subtext">Requires diagnostic inspection</span>
          </div>
        </div>

        <div className="kpi-card card">
          <div className="kpi-icon kpi-purple">
            <Database size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Cache Hit Ratio</span>
            <span className="kpi-value">{loading ? '...' : `${cacheHitRate}%`}</span>
            <span className="kpi-subtext">Domain resolution speedup</span>
          </div>
        </div>

        <div className="kpi-card card">
          <div className="kpi-icon kpi-emerald">
            <Zap size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Throughput</span>
            <span className="kpi-value">{loading ? '...' : `${throughputSpeed} rows/s`}</span>
            <span className="kpi-subtext">Parallel batch execution</span>
          </div>
        </div>

        <div className="kpi-card card">
          <div className="kpi-icon kpi-indigo">
            <ShieldCheck size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Verification Rate</span>
            <span className="kpi-value">{loading ? '...' : `${verificationRate}%`}</span>
            <span className="kpi-subtext">Deliverability validity</span>
          </div>
        </div>

        <div className="kpi-card card">
          <div className="kpi-icon kpi-teal">
            <Cpu size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Active Workers</span>
            <span className="kpi-value">{loading ? '...' : activeWorkers}</span>
            <span className="kpi-subtext">Cluster worker nodes</span>
          </div>
        </div>
      </div>

      {/* Recent Jobs Section */}
      <div className="card mt-4">
        <div className="card-header-flex">
          <div>
            <h3>Recent Enrichment Jobs</h3>
            <p className="subtitle">Latest batch execution logs and progress</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/jobs')}>
            View All Jobs <ArrowRight size={16} />
          </button>
        </div>

        <div className="table-container mt-3">
          <table className="table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>File Name</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Progress</th>
                <th>Created</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {recentJobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center text-muted">
                    No jobs processed yet. Click "Upload New CSV" to get started.
                  </td>
                </tr>
              ) : (
                recentJobs.map((j) => (
                  <tr key={j.job_id}>
                    <td>
                      <code className="code-badge">{(j.job_id || '').substring(0, 8)}...</code>
                    </td>
                    <td>{j.original_filename || 'Untitled'}</td>
                    <td>
                      <span className={`badge badge-${j.status === 'completed' ? 'success' : j.status === 'failed' ? 'danger' : 'warning'}`}>
                        {j.status || 'UNKNOWN'}
                      </span>
                    </td>
                    <td>{j.row_count ?? 0}</td>
                    <td>
                      <div className="progress-bar-container">
                        <div className="progress-bar-fill" style={{ width: `${j.progress_percentage ?? 0}%` }}></div>
                        <span className="progress-text">{j.progress_percentage ?? 0}%</span>
                      </div>
                    </td>
                    <td>{j.created_at ? new Date(j.created_at).toLocaleTimeString() : '—'}</td>
                    <td>
                      <button className="btn btn-secondary btn-xs" onClick={() => navigate(`/jobs/${j.job_id}`)}>
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
