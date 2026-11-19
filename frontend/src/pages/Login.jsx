import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Input, Btn, ErrorAlert, FormField } from '../components/FormComponents';
import { Lock, User, Eye, EyeOff, CheckCircle2, AlertCircle } from 'lucide-react';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const reason = params.get('reason');

  const [form, setForm] = useState({ username: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(form.username, form.password);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const msg = err.response?.data?.detail ?? 'Login failed';
      if (typeof msg === 'string' && msg.toLowerCase().includes('lock')) {
        setError('Account locked due to too many failed attempts. Try again after 15 minutes.');
      } else {
        setError(typeof msg === 'string' ? msg : 'Invalid username or password');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-indigo-50 p-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-6">
          <div className="text-5xl mb-3">💊</div>
          <h1 className="text-2xl font-bold text-gray-900">PharmaTrack-X</h1>
          <p className="text-sm text-gray-500 mt-1">Pharmacy Inventory Decision Support System</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8">
          {/* Status feedback messages */}
          {reason === 'logged_out' && (
            <div className="mb-4 p-3 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2">
              <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
              <span>You have been logged out successfully.</span>
            </div>
          )}

          {reason === 'session_expired' && (
            <div className="mb-4 p-3 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
              <AlertCircle size={16} className="text-amber-600 shrink-0" />
              <span>Your session has expired. Please log in again.</span>
            </div>
          )}

          {reason === 'timeout' && (
            <div className="mb-4 p-3 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
              <AlertCircle size={16} className="text-amber-600 shrink-0" />
              <span>Your session expired due to inactivity. Please log in again.</span>
            </div>
          )}

          {reason === 'unauthorized' && (
            <div className="mb-4 p-3 text-sm text-red-800 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
              <AlertCircle size={16} className="text-red-600 shrink-0" />
              <span>Access denied. Please log in with an authorized account.</span>
            </div>
          )}

          <ErrorAlert message={error} />

          <form onSubmit={handleSubmit} className="mt-4 space-y-4" autoComplete="off">
            <FormField label="Username" required>
              <div className="relative">
                <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Enter username"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  className="pl-9"
                  autoFocus
                  required
                />
              </div>
            </FormField>

            <FormField label="Password" required>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <Input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="pl-9 pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 focus:outline-none p-1"
                  title={showPassword ? 'Hide password' : 'Show password'}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </FormField>

            <Btn type="submit" className="w-full justify-center py-2.5 text-base font-semibold" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </Btn>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          PharmaTrack-X v1.0 — NED CIS 2026
        </p>
      </div>
    </div>
  );
}
