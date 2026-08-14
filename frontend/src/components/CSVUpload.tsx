import React, { useState, useRef, useEffect } from 'react';
import { ApiService } from '../services/api';
import { JobUploadResponse, QueueJobResponse, JobDetailResponse } from '../types';

export const CSVUpload: React.FC = () => {
  const [uploading, setUploading] = useState<boolean>(false);
  const [queueing, setQueueing] = useState<boolean>(false);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<JobUploadResponse | null>(null);
  const [queueResult, setQueueResult] = useState<QueueJobResponse | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetailResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let interval: any = null;
    if (uploadResult?.job_id && (queueResult || jobDetail?.status === 'PROCESSING' || jobDetail?.status === 'QUEUED')) {
      interval = setInterval(async () => {
        try {
          const detail = await ApiService.getJobDetail(uploadResult.job_id);
          setJobDetail(detail);
          if (detail.status === 'COMPLETED' || detail.status === 'FAILED') {
            if (interval) clearInterval(interval);
          }
        } catch (err) {
          console.error('Error polling job status:', err);
        }
      }, 1500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [uploadResult, queueResult, jobDetail?.status]);

  const handleFileSelect = async (file: File) => {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Unsupported file format. Only .csv files are supported.');
      return;
    }

    if (file.size > 20 * 1024 * 1024) {
      setError('File size exceeds the maximum limit of 20MB.');
      return;
    }

    setError(null);
    setUploading(true);
    setQueueResult(null);
    setJobDetail(null);

    try {
      const response = await ApiService.uploadCSV(file);
      setUploadResult(response);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred during CSV upload.';
      setError(message);
      setUploadResult(null);
    } finally {
      setUploading(false);
    }
  };

  const handleQueueJob = async () => {
    if (!uploadResult?.job_id) return;

    setQueueing(true);
    setError(null);

    try {
      console.log(`Queueing Job: ${uploadResult.job_id}`);
      const qRes = await ApiService.queueJob(uploadResult.job_id);
      setQueueResult(qRes);
      // Fetch initial job detail
      const detail = await ApiService.getJobDetail(uploadResult.job_id);
      setJobDetail(detail);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to queue job for background processing.';
      setError(message);
    } finally {
      setQueueing(false);
    }
  };

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(true);
  };

  const onDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const resetUpload = () => {
    setUploadResult(null);
    setQueueResult(null);
    setJobDetail(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const currentStatus = jobDetail?.status || queueResult?.status || uploadResult?.status || 'VALIDATED';
  const processedRows = jobDetail?.processed_rows || 0;
  const totalRows = uploadResult?.rows || jobDetail?.total_rows || 1;
  const progressPercent = Math.min(100, Math.round((processedRows / totalRows) * 100));

  return (
    <div className="card" style={{ marginTop: '1.5rem' }}>
      <div style={{ marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Bulk CSV File Upload & Queue Engine</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
          Upload a CSV dataset, queue the job, and track real-time enrichment execution.
        </p>
      </div>

      {error && (
        <div className="alert alert-danger">
          <span>⚠️ {error}</span>
        </div>
      )}

      {!uploadResult ? (
        <div
          className={`drop-zone ${dragOver ? 'active' : ''}`}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            type="file"
            ref={fileInputRef}
            accept=".csv"
            style={{ display: 'none' }}
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                handleFileSelect(e.target.files[0]);
              }
            }}
          />

          <div className="drop-zone-icon">
            <svg width="28" height="28" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>

          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              {uploading ? 'Validating & Uploading CSV...' : 'Drag & drop your CSV file here, or click to browse'}
            </h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Required column: <strong style={{ color: 'var(--text-primary)' }}>Company</strong> • Max file size: 20MB • Max rows: 10,000
            </p>
          </div>

          {!uploading && (
            <button type="button" className="btn btn-primary" style={{ marginTop: '0.5rem' }}>
              Select CSV File
            </button>
          )}
        </div>
      ) : (
        <div>
          <div className="alert alert-success" style={{ marginBottom: '1.5rem' }}>
            <div>
              <strong>✅ CSV Validated & Uploaded Successfully!</strong>
              <div style={{ marginTop: '0.25rem' }}>
                Job ID: <code>{uploadResult.job_id}</code>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Status</span>
              <div style={{ marginTop: '0.25rem' }}>
                <span className={`badge ${currentStatus === 'COMPLETED' ? 'badge-success' : currentStatus === 'QUEUED' || currentStatus === 'PROCESSING' ? 'badge-info' : ''}`}>
                  {currentStatus}
                </span>
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Total Rows</span>
              <div style={{ fontWeight: 600, fontSize: '1.1rem', marginTop: '0.25rem' }}>
                {uploadResult.rows.toLocaleString()} rows
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Queue Position</span>
              <div style={{ fontWeight: 600, fontSize: '1.1rem', marginTop: '0.25rem' }}>
                {queueResult ? `#${queueResult.queue_position}` : 'Not Queued'}
              </div>
            </div>

            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Original Filename</span>
              <div style={{ fontWeight: 600, marginTop: '0.25rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {uploadResult.original_filename}
              </div>
            </div>
          </div>

          {/* Live Progress Bar if Queued or Processing */}
          {(currentStatus === 'QUEUED' || currentStatus === 'PROCESSING' || currentStatus === 'COMPLETED') && (
            <div style={{ marginBottom: '1.5rem', background: 'rgba(255,255,255,0.02)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.875rem' }}>
                <span>Worker Progress: {processedRows} / {totalRows} rows</span>
                <span>{progressPercent}%</span>
              </div>
              <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: `${progressPercent}%`, height: '100%', background: currentStatus === 'COMPLETED' ? '#10b981' : '#3b82f6', transition: 'width 0.3s ease' }} />
              </div>
              {jobDetail && (
                <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', gap: '1rem' }}>
                  <span>Success: <strong style={{ color: '#10b981' }}>{jobDetail.successful_rows}</strong></span>
                  <span>Failed: <strong style={{ color: '#ef4444' }}>{jobDetail.failed_rows}</strong></span>
                </div>
              )}
            </div>
          )}

          {uploadResult.warnings && uploadResult.warnings.length > 0 && (
            <div className="alert alert-warning" style={{ marginBottom: '1.5rem' }}>
              <ul style={{ listStylePosition: 'inside', margin: 0 }}>
                {uploadResult.warnings.map((warn, idx) => (
                  <li key={idx}>⚠️ {warn}</li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h4 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              Data Preview (First {uploadResult.preview.length} Rows)
            </h4>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    {uploadResult.headers.map((h, i) => (
                      <th key={i}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {uploadResult.preview.map((row, rIdx) => (
                    <tr key={rIdx}>
                      {uploadResult.headers.map((h, cIdx) => (
                        <td key={cIdx}>{row[h] || '-'}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            {!queueResult && currentStatus === 'VALIDATED' && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleQueueJob}
                disabled={queueing}
              >
                {queueing ? 'Queueing Job...' : '🚀 Start Enrichment Pipeline (Queue Job)'}
              </button>
            )}

            <button type="button" className="btn btn-secondary" onClick={resetUpload}>
              Upload Another CSV
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
