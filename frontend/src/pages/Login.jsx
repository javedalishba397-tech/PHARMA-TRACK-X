import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Input, Btn, ErrorAlert, FormField } from '../components/FormComponents';
import { Lock, User } from 'lucide-react';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const reason = params.get('reason');

  const [form, setForm] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(form.username, form.password);
      navigate('/dashboard');
    } catch (err) {
      const msg = err.response?.data?.detail ?? 'Login failed';
      if (typeof msg === 'string' && msg.toLowerCase().includes('lock')) {
        setError('Account locked due to too many failed attempts. Try again after 15 minutes.');
      } else {
        setError(typeof msg === 'string' ? msg : 'Invalid credentials');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-white to-indigo-50 p-4">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="text-5xl mb-3">💊</div>
          <h1 className="text-2xl font-bold text-gray-900">PharmaTrack-X</h1>
          <p className="text-sm text-gray-500 mt-1">Pharmacy Inventory Decision Support</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8">
          {reason === 'timeout' && (
            <div className="mb-4 p-3 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg">
              Your session expired due to inactivity. Please log in again.
            </div>
          )}

          <ErrorAlert message={error} />

          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <FormField label="Username" required>
              <div className="relative">
                <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <Input
                  type="text" placeholder="Enter username"
                  value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })}
                  className="pl-9" autoFocus required />
              </div>
            </FormField>

            <FormField label="Password" required>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <Input
                  type="password" placeholder="Enter password"
                  value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="pl-9" required />
              </div>
            </FormField>

            <Btn type="submit" className="w-full justify-center" disabled={loading}>
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
