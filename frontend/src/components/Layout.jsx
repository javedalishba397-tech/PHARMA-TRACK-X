import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard, Pill, ShoppingCart, Truck, Package,
  BarChart3, Settings, LogOut, AlertCircle, ClipboardList, Users
} from 'lucide-react';
import Badge from './Badge';

export default function Layout({ children }) {
  const { user, logout, isRole, inactivityWarning, resetInactivityTimer } = useAuth();

  const handleLogout = () => {
    logout('logged_out');
  };

  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['admin','pharmacist','clerk'] },
    { to: '/medicines', label: 'Medicines', icon: Pill, roles: ['admin','pharmacist','clerk'] },
    { to: '/sales', label: isRole('pharmacist', 'clerk') ? 'Point of Sale' : 'Sales & Invoices', icon: ShoppingCart, roles: ['admin','pharmacist','clerk'] },
    { to: '/purchases', label: 'Purchases', icon: Truck, roles: ['admin','pharmacist'] },
    { to: '/stock', label: 'Stock & Alerts', icon: Package, roles: ['admin','pharmacist'] },
    { to: '/recommendations', label: 'Recommendations', icon: ClipboardList, roles: ['admin','pharmacist'] },
    { to: '/reports', label: 'Reports', icon: BarChart3, roles: ['admin','pharmacist'] },
    { to: '/settings', label: 'Settings', icon: Settings, roles: ['admin'] },
  ];

  const visible = navItems.filter((n) => isRole(...n.roles));

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 bg-white border-r border-gray-200 flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <span className="text-2xl">💊</span>
            <div>
              <p className="text-sm font-bold text-gray-900 leading-tight">PharmaTrack-X</p>
              <p className="text-xs text-gray-400">Inventory DSS v1.0</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2">
          {visible.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium mb-0.5 transition-fast
                 ${isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'}`}>
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User info */}
        <div className="px-3 py-3 border-t border-gray-200">
          <div className="flex items-center gap-2 px-2 py-2 rounded-lg">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-bold text-xs shrink-0">
              {user?.full_name?.[0] ?? user?.username?.[0] ?? '?'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-gray-800 truncate">{user?.full_name ?? user?.username}</p>
              <Badge label={user?.role} className="mt-0.5" />
            </div>
          </div>
          <button onClick={handleLogout}
            className="mt-1 w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded-lg transition-fast">
            <LogOut size={14} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Inactivity warning banner */}
        {inactivityWarning && (
          <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-between">
            <div className="flex items-center gap-2 text-amber-800 text-sm">
              <AlertCircle size={16} />
              Your session will expire in ~1 minute due to inactivity.
            </div>
            <button onClick={resetInactivityTimer}
              className="px-3 py-1 text-xs bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition-fast">
              Stay logged in
            </button>
          </div>
        )}

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
