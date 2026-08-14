import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';
import { ToastProvider } from './components/Toast';
import { ProtectedRoute } from './components/ProtectedRoute';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { UploadPage } from './pages/UploadPage';
import { JobsPage } from './pages/JobsPage';
import { JobDetailPage } from './pages/JobDetailPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { WorkersPage } from './pages/WorkersPage';
import { SettingsPage } from './pages/SettingsPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const App: React.FC = () => {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Authentication Route */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Application Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<MainLayout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="upload" element={<UploadPage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="jobs/:jobId" element={<JobDetailPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="workers" element={<WorkersPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
};

export default App;
