import React, { useState } from 'react';
import { Save, Server, Shield, Sliders, Key } from 'lucide-react';
import { useToast } from '../components/Toast';

export const SettingsPage: React.FC = () => {
  const [apiUrl, setApiUrl] = useState(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000');
  const [verificationProvider, setVerificationProvider] = useState('mock');
  const [tavilyKey, setTavilyKey] = useState(localStorage.getItem('settings_tavily_key') || '');
  const [braveKey, setBraveKey] = useState(localStorage.getItem('settings_brave_key') || '');
  const [openaiKey, setOpenaiKey] = useState(localStorage.getItem('settings_openai_key') || '');
  const [batchSize, setBatchSize] = useState('50');
  const [domainConcurrency, setDomainConcurrency] = useState('20');
  const { addToast } = useToast();

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem('settings_api_url', apiUrl);
    localStorage.setItem('settings_verification_provider', verificationProvider);
    localStorage.setItem('settings_tavily_key', tavilyKey);
    localStorage.setItem('settings_brave_key', braveKey);
    localStorage.setItem('settings_openai_key', openaiKey);
    localStorage.setItem('settings_batch_size', batchSize);
    localStorage.setItem('settings_domain_concurrency', domainConcurrency);

    addToast('success', 'Settings Saved', 'Platform configurations and API provider keys saved successfully.');
  };

  return (
    <div className="settings-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Platform Configuration Settings</h1>
          <p className="page-subtitle">Configure backend REST endpoints, domain resolution fallback providers & API keys</p>
        </div>
      </div>

      <div className="card">
        <form onSubmit={handleSave} className="settings-form">
          <div className="form-group mb-4">
            <label className="form-label">
              <Server size={18} /> Backend API Endpoint URL
            </label>
            <input
              type="text"
              className="form-control"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="http://127.0.0.1:8000"
            />
            <span className="form-hint">Base URL for FastAPI REST endpoints</span>
          </div>

          <div className="form-group mb-4">
            <label className="form-label">
              <Shield size={18} /> Default Verification Provider
            </label>
            <select
              className="form-control"
              value={verificationProvider}
              onChange={(e) => setVerificationProvider(e.target.value)}
            >
              <option value="mock">Mock Provider (Offline Testing)</option>
              <option value="smtp">SMTP & MX Provider (Real Mailbox Probing)</option>
              <option value="hunter">Hunter.io API Provider</option>
              <option value="zerobounce">ZeroBounce API Provider</option>
              <option value="neverbounce">NeverBounce API Provider</option>
            </select>
          </div>

          {/* Domain Provider Keys Section */}
          <div className="border-t border-gray-700 pt-4 mt-4">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <Key size={18} /> Domain Resolution Provider Keys
            </h3>
            <div className="form-group mb-4">
              <label className="form-label">Tavily Search API Key</label>
              <input
                type="password"
                className="form-control"
                value={tavilyKey}
                onChange={(e) => setTavilyKey(e.target.value)}
                placeholder="tvly-..."
              />
              <span className="form-hint">Primary search API for domain resolution fallback</span>
            </div>

            <div className="form-group mb-4">
              <label className="form-label">Brave Search API Key</label>
              <input
                type="password"
                className="form-control"
                value={braveKey}
                onChange={(e) => setBraveKey(e.target.value)}
                placeholder="BSA..."
              />
              <span className="form-hint">Secondary web search API fallback</span>
            </div>

            <div className="form-group mb-4">
              <label className="form-label">OpenAI API Key (Heuristic Domain Deductions)</label>
              <input
                type="password"
                className="form-control"
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
                placeholder="sk-proj-..."
              />
              <span className="form-hint">AI domain guessing fallback when search providers yield no results</span>
            </div>
          </div>

          <div className="form-group mb-4">
            <label className="form-label">
              <Sliders size={18} /> Email Verification Batch Chunk Size
            </label>
            <input
              type="number"
              className="form-control"
              value={batchSize}
              onChange={(e) => setBatchSize(e.target.value)}
              min="10"
              max="500"
            />
            <span className="form-hint">Candidate emails grouped per batch verification request (Default: 50)</span>
          </div>

          <div className="form-group mb-4">
            <label className="form-label">
              <Sliders size={18} /> Parallel Domain Resolution Concurrency
            </label>
            <input
              type="number"
              className="form-control"
              value={domainConcurrency}
              onChange={(e) => setDomainConcurrency(e.target.value)}
              min="5"
              max="50"
            />
            <span className="form-hint">Simultaneous company domain lookup tasks per worker (Default: 20)</span>
          </div>

          <div className="action-row mt-4">
            <button type="submit" className="btn btn-primary">
              <Save size={18} /> Save Settings
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
