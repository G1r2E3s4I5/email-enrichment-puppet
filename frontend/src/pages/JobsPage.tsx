import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Filter, RefreshCw, Eye, StopCircle } from 'lucide-react';
import { ApiService } from '../services/api';
import { JobSummary } from '../types';
import { useToast } from '../components/Toast';

export const JobsPage: React.FC = () => {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const limit = 10;
  const navigate = useNavigate();
  const { addToast } = useToast();

  const loadJobs = async () => {
    try {
      setLoading(true);
      const res = await ApiService.getJobsList(statusFilter, limit, page * limit);
      setJobs(res.jobs);
      setTotalCount(res.total_count);
    } catch (err) {
      console.error('Error fetching jobs:', err);
      addToast('error', 'Failed to Load Jobs', 'Could not retrieve jobs from server.');
    } finally {
      setLoading(false);
    }
  };

  const handleStopJob = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to stop processing for this job?')) {
      return;
    }
    try {
      await ApiService.stopJob(jobId);
      addToast('warning', 'Job Processing Stopped', 'Processing cancelled and worker stopped.');
      await loadJobs();
    } catch (err: any) {
      console.error('Failed to stop job:', err);
      addToast('error', 'Stop Failed', err.message || 'Failed to stop job.');
    }
  };

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 6000);
    return () => clearInterval(interval);
  }, [statusFilter, page]);

  const filteredJobs = (jobs || []).filter((j) =>
    (j.original_filename || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (j.job_id || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="jobs-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Job Management & Execution Queue</h1>
          <p className="page-subtitle">Monitor processing status, row completion, verification rates & historical runs</p>
        </div>
        <button className="btn btn-secondary" onClick={loadJobs} title="Refresh Jobs">
          <RefreshCw size={16} /> Refresh
        </button>
      </div>

      {/* Filter Toolbar */}
      <div className="card toolbar-card">
        <div className="search-bar">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            placeholder="Search by job ID or file name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="form-control"
          />
        </div>

        <div className="filter-group">
          <Filter size={18} className="text-secondary" />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
            className="form-control"
          >
            <option value="all">All Statuses</option>
            <option value="processing">Processing</option>
            <option value="queued">Queued</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="card">
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>File Name</th>
                <th>Status</th>
                <th>Total Rows</th>
                <th>Success / Fail</th>
                <th>Progress</th>
                <th>Duration</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && jobs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center text-muted">
                    Loading jobs from cluster worker queue...
                  </td>
                </tr>
              ) : filteredJobs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center text-muted">
                    No jobs found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredJobs.map((j) => (
                  <tr key={j.job_id}>
                    <td>
                      <code className="code-badge">{j.job_id.substring(0, 8)}...</code>
                    </td>
                    <td>
                      <strong>{j.original_filename}</strong>
                    </td>
                    <td>
                      <span className={`badge badge-${(j.status || '').toLowerCase() === 'completed' ? 'success' : (j.status || '').toLowerCase() === 'failed' || (j.status || '').toLowerCase() === 'cancelled' ? 'danger' : 'warning'}`}>
                        {j.status}
                      </span>
                    </td>
                    <td>{j.row_count}</td>
                    <td>
                      <span className="text-success">{j.successful_rows}</span> / <span className="text-danger">{j.failed_rows}</span>
                    </td>
                    <td>
                      <div className="progress-bar-container">
                        <div className="progress-bar-fill" style={{ width: `${j.progress_percentage}%` }}></div>
                        <span className="progress-text">{j.progress_percentage}%</span>
                      </div>
                    </td>
                    <td>{j.duration_sec !== undefined && j.duration_sec !== null ? `${j.duration_sec.toFixed(1)}s` : 'Processing'}</td>
                    <td>{j.created_at ? new Date(j.created_at).toLocaleTimeString() : '—'}</td>
                    <td>
                      <div className="action-buttons" style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        {((j.status || '').toLowerCase() === 'processing' || (j.status || '').toLowerCase() === 'queued' || (j.status || '').toLowerCase() === 'validated') && (
                          <button
                            className="btn btn-danger btn-xs"
                            onClick={(e) => handleStopJob(j.job_id, e)}
                            title="Stop Processing Job"
                            style={{ backgroundColor: '#dc2626', color: '#fff', border: '1px solid #b91c1c' }}
                          >
                            <StopCircle size={14} /> Stop
                          </button>
                        )}
                        <button
                          className="btn btn-secondary btn-xs"
                          onClick={() => navigate(`/jobs/${j.job_id}`)}
                          title="View Job Details"
                        >
                          <Eye size={14} /> View
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        <div className="pagination-bar">
          <span>Showing page {page + 1} of {Math.ceil(totalCount / limit) || 1} ({totalCount} total jobs)</span>
          <div className="pagination-buttons">
            <button
              className="btn btn-secondary btn-xs"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              Previous
            </button>
            <button
              className="btn btn-secondary btn-xs"
              disabled={(page + 1) * limit >= totalCount}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
