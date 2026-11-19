import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { authApi, setAuthToken } from '../api/client';

const AuthContext = createContext(null);

const INACTIVITY_LIMIT_MS = 15 * 60 * 1000; // 15 minutes
const WARNING_BEFORE_MS = 60 * 1000;         // warn 1 minute before logout

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [inactivityWarning, setInactivityWarning] = useState(false);

  const inactivityTimer = useRef(null);
  const warningTimer = useRef(null);
  const authChannelRef = useRef(null);

  // Secure server-side logout
  const logout = useCallback(async (reason = 'logged_out') => {
    try {
      await authApi.logout();
    } catch (err) {
      console.warn('Server logout error:', err);
    }
    // Clear in-memory token and state
    setAuthToken(null);
    setUser(null);
    setInactivityWarning(false);
    clearTimeout(inactivityTimer.current);
    clearTimeout(warningTimer.current);

    // Notify other open tabs to synchronize logout
    try {
      if (authChannelRef.current) {
        authChannelRef.current.postMessage({ type: 'LOGOUT' });
      }
    } catch (e) {}

    // Replace history entry to prevent browser back navigation to protected pages
    if (typeof window !== 'undefined') {
      window.history.replaceState(null, '', `/login?reason=${reason}`);
      window.location.replace(`/login?reason=${reason}`);
    }
  }, []);

  // Inactivity timeout handler
  const resetInactivityTimer = useCallback(() => {
    if (!user) return;
    clearTimeout(inactivityTimer.current);
    clearTimeout(warningTimer.current);
    setInactivityWarning(false);

    warningTimer.current = setTimeout(() => {
      setInactivityWarning(true);
    }, INACTIVITY_LIMIT_MS - WARNING_BEFORE_MS);

    inactivityTimer.current = setTimeout(() => {
      logout('timeout');
    }, INACTIVITY_LIMIT_MS);
  }, [user, logout]);

  // Track user activity to refresh inactivity timer
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

  // Initial session validation on startup
  const checkSession = useCallback(async () => {
    try {
      const res = await authApi.me();
      if (res.data && res.data.is_active) {
        setUser(res.data);
      } else {
        setUser(null);
      }
    } catch (err) {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  // Multi-tab logout synchronization & BFCache / PopState protection
  useEffect(() => {
    // 1. BroadcastChannel for cross-tab communication
    try {
      const channel = new BroadcastChannel('pharmatrack_auth');
      authChannelRef.current = channel;
      channel.onmessage = (event) => {
        if (event.data?.type === 'LOGOUT') {
          setAuthToken(null);
          setUser(null);
          if (window.location.pathname !== '/login') {
            window.history.replaceState(null, '', '/login?reason=logged_out');
            window.location.replace('/login?reason=logged_out');
          }
        }
      };
    } catch (e) {
      console.warn('BroadcastChannel not supported:', e);
    }

    // 2. BFCache protection: pageshow event
    const handlePageShow = async (event) => {
      if (event.persisted) {
        try {
          const res = await authApi.me();
          if (res.data && res.data.is_active) {
            setUser(res.data);
          } else {
            setUser(null);
            if (window.location.pathname !== '/login') {
              window.history.replaceState(null, '', '/login?reason=session_expired');
              window.location.replace('/login?reason=session_expired');
            }
          }
        } catch {
          setUser(null);
          if (window.location.pathname !== '/login') {
            window.history.replaceState(null, '', '/login?reason=session_expired');
            window.location.replace('/login?reason=session_expired');
          }
        }
      }
    };

    // 3. Popstate protection: browser Back/Forward navigation
    const handlePopState = async () => {
      if (window.location.pathname !== '/login') {
        try {
          const res = await authApi.me();
          if (!res.data || !res.data.is_active) {
            setUser(null);
            window.history.replaceState(null, '', '/login?reason=session_expired');
            window.location.replace('/login?reason=session_expired');
          }
        } catch {
          setUser(null);
          window.history.replaceState(null, '', '/login?reason=session_expired');
          window.location.replace('/login?reason=session_expired');
        }
      }
    };

    window.addEventListener('pageshow', handlePageShow);
    window.addEventListener('popstate', handlePopState);

    return () => {
      window.removeEventListener('pageshow', handlePageShow);
      window.removeEventListener('popstate', handlePopState);
      if (authChannelRef.current) {
        authChannelRef.current.close();
      }
    };
  }, []);

  const login = async (username, password) => {
    const res = await authApi.login(username, password);
    const { access_token, user: userData } = res.data;
    setAuthToken(access_token);
    setUser(userData);
    return userData;
  };

  // Backend roles: "Administrator", "Pharmacist", "Sales Clerk"
  // Frontend shorthand: "admin", "pharmacist", "clerk"
  const ROLE_MAP = { admin: 'Administrator', pharmacist: 'Pharmacist', clerk: 'Sales Clerk' };
  const isRole = (...shortRoles) => shortRoles.some((r) => (ROLE_MAP[r] ?? r) === user?.role);
  const hasPermission = (perm) => user?.permissions?.includes(perm);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        isRole,
        hasPermission,
        inactivityWarning,
        resetInactivityTimer,
        checkSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
