import { useEffect, useRef } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/client';
import { PageLoader } from './Spinner';

// Map shorthand role names to backend values
const ROLE_MAP = { admin: 'Administrator', pharmacist: 'Pharmacist', clerk: 'Sales Clerk' };

export default function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  const reportedRef = useRef(false);

  // Check if route requires Administrator role
  const isAdminRoute = roles && roles.length === 1 && roles.includes('admin');
  const isUnauthorized = !user || (roles && roles.length > 0 && !roles.map((r) => ROLE_MAP[r] ?? r).includes(user?.role));

  // Automatically record unauthorized attempts to access admin URLs into the Admin Audit Log
  useEffect(() => {
    if (!loading && isUnauthorized && isAdminRoute && !reportedRef.current) {
      reportedRef.current = true;
      const desc = !user
        ? `Unauthenticated visitor attempted direct URL search bar navigation to ${location.pathname}`
        : `User '${user.username}' (${user.role}) attempted direct URL search bar navigation to ${location.pathname}`;
      authApi.reportUnauthorized(location.pathname, desc).catch(() => {});
    }
  }, [loading, isUnauthorized, isAdminRoute, user, location.pathname]);

  // Do not expose protected content while session verification is pending
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <PageLoader />
      </div>
    );
  }

  // Not authenticated -> redirect to login with unauthorized notice
  if (!user) {
    return <Navigate to="/login?reason=unauthorized" replace />;
  }

  // Role-Based Access Control check -> redirect unauthorized non-admin back to dashboard
  if (roles && roles.length > 0) {
    const expanded = roles.map((r) => ROLE_MAP[r] ?? r);
    if (!expanded.includes(user.role)) {
      return <Navigate to="/dashboard" replace />;
    }
  }

  return children;
}
