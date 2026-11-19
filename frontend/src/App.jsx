import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';

import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Medicines from './pages/Medicines';
import Sales from './pages/Sales';
import Purchases from './pages/Purchases';
import Stock from './pages/Stock';
import Recommendations from './pages/Recommendations';
import Reports from './pages/Reports';
import SettingsPage from './pages/Settings';

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      {/* All roles */}
      <Route path="/dashboard" element={
        <ProtectedRoute roles={['admin','pharmacist','clerk']}>
          <Layout><Dashboard /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/medicines" element={
        <ProtectedRoute roles={['admin','pharmacist','clerk']}>
          <Layout><Medicines /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/sales" element={
        <ProtectedRoute roles={['admin','pharmacist','clerk']}>
          <Layout><Sales /></Layout>
        </ProtectedRoute>
      } />

      {/* Admin + Pharmacist only */}
      <Route path="/purchases" element={
        <ProtectedRoute roles={['admin','pharmacist']}>
          <Layout><Purchases /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/stock" element={
        <ProtectedRoute roles={['admin','pharmacist']}>
          <Layout><Stock /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/recommendations" element={
        <ProtectedRoute roles={['admin','pharmacist']}>
          <Layout><Recommendations /></Layout>
        </ProtectedRoute>
      } />
      <Route path="/reports" element={
        <ProtectedRoute roles={['admin','pharmacist']}>
          <Layout><Reports /></Layout>
        </ProtectedRoute>
      } />

      {/* Admin only */}
      <Route path="/settings" element={
        <ProtectedRoute roles={['admin']}>
          <Layout><SettingsPage /></Layout>
        </ProtectedRoute>
      } />

      {/* Default redirects */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ErrorBoundary>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </ErrorBoundary>
    </AuthProvider>
  );
}
