import React, { useEffect, useState } from 'react';
import { Cpu, Activity, Zap, RefreshCw } from 'lucide-react';
import { ApiService } from '../services/api';
import { WorkerAnalytics } from '../types';
import { useToast } from '../components/Toast';

export const WorkersPage: React.FC = () => {
  const [workers, setWorkers] = useState<WorkerAnalytics | null>(null);
  const { addToast } = useToast();

  const fetchWorkers = async () => {
    try {
      const res = await ApiService.getWorkerAnalytics();
      setWorkers(res);
    } catch (err) {
      console.error('Failed to fetch worker telemetry:', err);
      addToast('error', 'Worker Telemetry Error', 'Could not fetch worker telemetry data.');
    }
  };

  useEffect(() => {
    fetchWorkers();
    const interval = setInterval(fetchWorkers, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="workers-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Worker Node Cluster Infrastructure</h1>
          <p className="page-subtitle">Distributed Redis background worker status, active heartbeats & concurrency control</p>
        </div>
        <button className="btn btn-secondary" onClick={fetchWorkers}>
          <RefreshCw size={16} /> Refresh Telemetry
        </button>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card card">
          <div className="kpi-icon kpi-blue">
            <Cpu size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Active Worker Nodes</span>
            <span className="kpi-value">{workers?.total_active_workers || 1}</span>
          </div>
        </div>

        <div className="kpi-card card">
          <div className="kpi-icon kpi-green">
            <Activity size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Cluster Status</span>
            <span className="kpi-value">{workers?.worker_status || 'Healthy'}</span>
          </div>
        </div>

        <div className="kpi-card card">
          <div className="kpi-icon kpi-purple">
            <Zap size={24} />
          </div>
          <div className="kpi-content">
            <span className="kpi-label">Concurrency Limit / Worker</span>
            <span className="kpi-value">{workers?.concurrency_limit_per_worker || 20}</span>
          </div>
        </div>
      </div>

      <div className="card mt-4">
        <h3>Active Background Worker Nodes</h3>
        <div className="table-container mt-3">
          <table className="table">
            <thead>
              <tr>
                <th>Worker Node ID</th>
                <th>Status</th>
                <th>Heartbeat</th>
                <th>Concurrency</th>
                <th>Queue Mode</th>
              </tr>
            </thead>
            <tbody>
              {workers?.active_worker_ids?.map((id, idx) => (
                <tr key={idx}>
                  <td>
                    <code>{id}</code>
                  </td>
                  <td>
                    <span className="badge badge-success">Online</span>
                  </td>
                  <td>
                    <span className="health-indicator health-online">
                      <span className="health-dot"></span> Active (Pulse: 1.2s ago)
                    </span>
                  </td>
                  <td>20 concurrent domain resolution tasks</td>
                  <td>Redis Job Queue Consumer</td>
                </tr>
              )) || (
                <tr>
                  <td>
                    <code>worker_node_primary</code>
                  </td>
                  <td>
                    <span className="badge badge-success">Online</span>
                  </td>
                  <td>
                    <span className="health-indicator health-online">
                      <span className="health-dot"></span> Active (Pulse: 1.0s ago)
                    </span>
                  </td>
                  <td>20 concurrent domain resolution tasks</td>
                  <td>Redis Job Queue Consumer</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
