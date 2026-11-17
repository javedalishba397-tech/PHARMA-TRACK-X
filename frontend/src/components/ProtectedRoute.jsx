import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

// Map shorthand role names to backend values
const ROLE_MAP = { admin: 'Administrator', pharmacist: 'Pharmacist', clerk: 'Sales Clerk' };

export default function ProtectedRoute({ children, roles }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (roles) {
    const expanded = roles.map(r => ROLE_MAP[r] ?? r);
    if (!expanded.includes(user.role)) return <Navigate to="/dashboard" replace />;
  }
  return children;
}
