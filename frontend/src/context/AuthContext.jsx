import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { authApi } from '../api/client';

const AuthContext = createContext(null);

const INACTIVITY_LIMIT_MS = 15 * 60 * 1000; // 15 minutes
const WARNING_BEFORE_MS = 60 * 1000;         // warn 1 minute before logout

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('ptx_user')); }
    catch { return null; }
  });
  const [token, setToken] = useState(() => localStorage.getItem('ptx_token'));
  const [inactivityWarning, setInactivityWarning] = useState(false);

  const inactivityTimer = useRef(null);
  const warningTimer = useRef(null);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    setInactivityWarning(false);
    localStorage.removeItem('ptx_token');
    localStorage.removeItem('ptx_user');
    clearTimeout(inactivityTimer.current);
    clearTimeout(warningTimer.current);
  }, []);

  const resetInactivityTimer = useCallback(() => {
    if (!user) return;
    clearTimeout(inactivityTimer.current);
    clearTimeout(warningTimer.current);
    setInactivityWarning(false);

    warningTimer.current = setTimeout(() => {
      setInactivityWarning(true);
    }, INACTIVITY_LIMIT_MS - WARNING_BEFORE_MS);

    inactivityTimer.current = setTimeout(() => {
      logout();
      window.location.href = '/login?reason=timeout';
    }, INACTIVITY_LIMIT_MS);
  }, [user, logout]);

  // Reset timer on user activity
  useEffect(() => {
    if (!user) return;
    const events = ['mousemove', 'keydown', 'mousedown', 'touchstart', 'scroll'];
    const handler = () => resetInactivityTimer();
    events.forEach((e) => window.addEventListener(e, handler));
    resetInactivityTimer();
    return () => {
      events.forEach((e) => window.removeEventListener(e, handler));
      clearTimeout(inactivityTimer.current);
      clearTimeout(warningTimer.current);
    };
  }, [user, resetInactivityTimer]);

  const login = async (username, password) => {
    const res = await authApi.login(username, password);
    const { access_token, user: userData } = res.data;
    localStorage.setItem('ptx_token', access_token);
    setToken(access_token);
    localStorage.setItem('ptx_user', JSON.stringify(userData));
    setUser(userData);
    return userData;
  };

  // Backend roles: "Administrator", "Pharmacist", "Sales Clerk"
  // Frontend shorthand: "admin", "pharmacist", "clerk"
  const ROLE_MAP = { admin: 'Administrator', pharmacist: 'Pharmacist', clerk: 'Sales Clerk' };
  const isRole = (...shortRoles) => shortRoles.some(r => (ROLE_MAP[r] ?? r) === user?.role);
  const hasPermission = (perm) => user?.permissions?.includes(perm);

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isRole, hasPermission, inactivityWarning, resetInactivityTimer }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
