import React, { useState } from 'react';
import { X, Download, FileText, FileSpreadsheet, Code } from 'lucide-react';
import { ApiService } from '../services/api';
import { ExportFormat, ExportFilter } from '../types';
import { useToast } from '../components/Toast';

interface ExportModalProps {
  jobId: string;
  filename: string;
  onClose: () => void;
}

export const ExportModal: React.FC<ExportModalProps> = ({ jobId, filename, onClose }) => {
  const [format, setFormat] = useState<ExportFormat>('csv');
  const [filter, setFilter] = useState<ExportFilter>('full');
  const [useStream, setUseStream] = useState(false);
  const [exporting, setExporting] = useState(false);
  const { addToast } = useToast();

  const handleDownload = () => {
    setExporting(true);
    try {
      const exportUrl = ApiService.getExportUrl(jobId, format, filter, useStream);
      
      // Trigger browser download via anchor element
      const link = document.createElement('a');
      link.href = exportUrl;
      link.setAttribute('download', '');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      addToast('success', 'Export Triggered', `Downloading ${filename} as ${format.toUpperCase()} (${filter})`);
      setTimeout(() => {
        setExporting(false);
        onClose();
      }, 1000);
    } catch (err: any) {
      console.error('Export download error:', err);
      addToast('error', 'Export Failed', err.message || 'Could not download export file');
      setExporting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Export Job Results</h3>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <p className="subtitle mb-3">Job ID: <code>{jobId.substring(0, 8)}...</code></p>

          <div className="form-group mb-4">
            <label className="form-label">Export File Format</label>
            <div className="format-selector-grid">
              <div
                className={`format-card ${format === 'csv' ? 'selected' : ''}`}
                onClick={() => setFormat('csv')}
              >
                <FileText size={24} />
                <div className="format-title">CSV File</div>
                <div className="format-sub">Standard spreadsheet</div>
              </div>

              <div
                className={`format-card ${format === 'xlsx' ? 'selected' : ''}`}
                onClick={() => setFormat('xlsx')}
              >
                <FileSpreadsheet size={24} />
                <div className="format-title">Excel (.xlsx)</div>
                <div className="format-sub">Microsoft Excel format</div>
              </div>

              <div
                className={`format-card ${format === 'json' ? 'selected' : ''}`}
                onClick={() => setFormat('json')}
              >
                <Code size={24} />
                <div className="format-title">JSON Payload</div>
                <div className="format-sub">Programmatic export</div>
              </div>
            </div>
          </div>

          <div className="form-group mb-4">
            <label className="form-label">Data Filtering Options</label>
            <select
              className="form-control"
              value={filter}
              onChange={(e) => setFilter(e.target.value as ExportFilter)}
            >
              <option value="full">Full Export (All rows & candidates)</option>
              <option value="top_ranked_only">Top-Ranked Only (Rank 1 candidate per row)</option>
              <option value="successful_only">Successful Rows Only (Valid enrichments)</option>
              <option value="failed_only">Failed Rows Only (Unresolved rows)</option>
            </select>
          </div>

          {(format === 'csv' || format === 'json') && (
            <div className="checkbox-group mb-4">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={useStream}
                  onChange={(e) => setUseStream(e.target.checked)}
                />
                <span>Enable streaming response chunking (Recommended for large datasets)</span>
              </label>
            </div>
          )}
        </div>

        <div className="modal-footer action-row flex-end">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleDownload} disabled={exporting}>
            {exporting ? 'Generating...' : <><Download size={18} /> Download {format.toUpperCase()} Export</>}
          </button>
        </div>
      </div>
    </div>
  );
};
