import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, LogIn, ShieldCheck } from 'lucide-react';
import { useToast } from '../components/Toast';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('admin@company.com');
  const [password, setPassword] = useState('admin123');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { addToast } = useToast();

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    setTimeout(() => {
      localStorage.setItem('auth_token', 'demo_token_123');
      localStorage.setItem('user_email', email);
      addToast('success', 'Logged In Successfully', `Welcome back, ${email}`);
      setLoading(false);
      navigate('/dashboard');
    }, 600);
  };

  return (
    <div className="login-page-container">
      <div className="login-card card">
        <div className="login-header">
          <div className="login-logo-icon">
            <Mail size={32} />
          </div>
          <h2>Email Enrichment Platform</h2>
          <p className="subtitle">Sign in to manage domain resolution & verification pipelines</p>
        </div>

        <form onSubmit={handleLogin} className="login-form">
          <div className="form-group">
            <label>Work Email Address</label>
            <div className="input-with-icon">
              <Mail size={18} className="input-icon" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@company.com"
                className="form-control"
              />
            </div>
          </div>

          <div className="form-group">
            <label>Password</label>
            <div className="input-with-icon">
              <Lock size={18} className="input-icon" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="form-control"
              />
            </div>
          </div>

          <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
            {loading ? 'Authenticating...' : <><LogIn size={18} /> Sign In</>}
          </button>

          <div className="login-footer-info">
            <ShieldCheck size={16} /> Enterprise SSO & Session Persistence Active
          </div>
        </form>
      </div>
    </div>
  );
};
