import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadCloud, FileText, CheckCircle2, AlertTriangle, Play } from 'lucide-react';
import { ApiService } from '../services/api';
import { JobUploadResponse } from '../types';
import { useToast } from '../components/Toast';

export const UploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadResponse, setUploadResponse] = useState<JobUploadResponse | null>(null);
  const [queueing, setQueueing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { addToast } = useToast();

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.name.endsWith('.csv')) {
        setFile(droppedFile);
      } else {
        addToast('error', 'Invalid File Format', 'Only .csv files are supported.');
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    try {
      setUploading(true);
      const res = await ApiService.uploadCSV(file);
      setUploadResponse(res);
      addToast('success', 'CSV Uploaded & Validated', `Job ${res.job_id.substring(0, 8)} created with ${res.rows} rows.`);
    } catch (err: any) {
      console.error('Upload error:', err);
      addToast('error', 'Upload Failed', err.message || 'Error uploading CSV file');
    } finally {
      setUploading(false);
    }
  };

  const handleQueueJob = async () => {
    if (!uploadResponse) return;
    try {
      setQueueing(true);
      await ApiService.queueJob(uploadResponse.job_id);
      addToast('success', 'Job Queued Successfully', 'Redis background workers have started processing this job.');
      navigate(`/jobs/${uploadResponse.job_id}`);
    } catch (err: any) {
      console.error('Queue error:', err);
      addToast('error', 'Queueing Failed', err.message || 'Failed to queue job');
    } finally {
      setQueueing(false);
    }
  };

  return (
    <div className="upload-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">CSV Dataset Upload</h1>
          <p className="page-subtitle">Upload company CSV files for automated parallel domain resolution & email verification</p>
        </div>
      </div>

      <div className="card">
        {!uploadResponse ? (
          <div
            className={`drop-zone ${dragActive ? 'active' : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
            <div className="drop-zone-icon">
              <UploadCloud size={32} />
            </div>

            {file ? (
              <div className="file-preview-info">
                <FileText size={24} className="text-primary" />
                <div>
                  <div className="file-name">{file.name}</div>
                  <div className="file-size">{(file.size / 1024).toFixed(1)} KB</div>
                </div>
              </div>
            ) : (
              <div>
                <p className="drop-title">Drag and drop your company CSV file here</p>
                <p className="drop-subtitle">or click to browse local files (Supports headers: Company, First Name, Last Name)</p>
              </div>
            )}

            {file && (
              <div className="action-row" onClick={(e) => e.stopPropagation()}>
                <button className="btn btn-primary" onClick={handleUpload} disabled={uploading}>
                  {uploading ? 'Validating CSV...' : <><UploadCloud size={18} /> Upload & Validate CSV</>}
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="upload-success-panel">
            <div className="alert alert-success">
              <CheckCircle2 size={20} />
              <div>
                <strong>CSV File Successfully Validated!</strong>
                <div>Job ID: <code>{uploadResponse.job_id}</code> | Total Rows: <strong>{uploadResponse.rows}</strong></div>
              </div>
            </div>

            {uploadResponse.warnings && uploadResponse.warnings.length > 0 && (
              <div className="alert alert-warning">
                <AlertTriangle size={20} />
                <div>
                  <strong>CSV Validation Warnings:</strong>
                  <ul>
                    {uploadResponse.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            <div className="preview-section">
              <h4>CSV File Header Mapping & Preview</h4>
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      {uploadResponse.headers.map((h, i) => (
                        <th key={i}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {uploadResponse.preview.slice(0, 5).map((row, i) => (
                      <tr key={i}>
                        {uploadResponse.headers.map((h, j) => (
                          <td key={j}>{row[h] || ''}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="action-row flex-end">
              <button className="btn btn-secondary" onClick={() => { setFile(null); setUploadResponse(null); }}>
                Choose Another File
              </button>
              <button className="btn btn-primary" onClick={handleQueueJob} disabled={queueing}>
                {queueing ? 'Queueing Job...' : <><Play size={18} /> Start Worker Processing Queue</>}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
