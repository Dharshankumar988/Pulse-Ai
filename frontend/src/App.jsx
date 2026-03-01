import { useState } from 'react';
import { AuthProvider, useAuth } from './AuthContext';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AdminPage from './pages/AdminPage';
import PatientsPage from './pages/PatientsPage';
import ChatPage from './pages/ChatPage';
import {
  Activity,
  LayoutDashboard,
  ShieldCheck,
  Users,
  MessageCircle,
  LogOut,
  Menu,
  X,
} from 'lucide-react';

const navItems = [
  { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { key: 'admin', label: 'Admin', icon: ShieldCheck, adminOnly: true },
  { key: 'patients', label: 'Patients', icon: Users },
  { key: 'chat', label: 'Assistant', icon: MessageCircle },
];

function Shell() {
  const { user, isAdmin, logout } = useAuth();
  const [tab, setTab] = useState('dashboard');
  const [mobileOpen, setMobileOpen] = useState(false);

  const visibleNav = navItems.filter(n => !n.adminOnly || isAdmin);

  const renderPage = () => {
    switch (tab) {
      case 'dashboard': return <DashboardPage />;
      case 'admin': return <AdminPage />;
      case 'patients': return <PatientsPage />;
      case 'chat': return <ChatPage />;
      default: return <DashboardPage />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top navigation bar */}
      <header className="glass-strong sticky top-0 z-50 px-5 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-teal-600/25 flex items-center justify-center glow-sm">
              <Activity size={20} className="text-teal-400" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">Pulse</span>
          </div>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            {visibleNav.map(n => {
              const Icon = n.icon;
              const active = tab === n.key;
              return (
                <button
                  key={n.key}
                  onClick={() => setTab(n.key)}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer
                    ${active
                      ? 'bg-teal-600/25 text-teal-300 shadow-[0_0_12px_rgba(13,148,136,0.25)]'
                      : 'text-slate-400 hover:text-white hover:bg-white/8'
                    }`}
                >
                  <Icon size={16} />
                  {n.label}
                </button>
              );
            })}
          </nav>

          {/* User + Logout */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/8 text-xs text-slate-300">
              <div className="w-2 h-2 rounded-full bg-emerald-400" />
              {user?.email}
              <span className="text-slate-500">|</span>
              <span className="text-teal-400">{user?.role}</span>
            </div>
            <button onClick={logout}
              className="w-9 h-9 rounded-xl bg-white/8 hover:bg-red-600/20 flex items-center justify-center text-slate-400 hover:text-red-400 transition cursor-pointer">
              <LogOut size={16} />
            </button>
            {/* Mobile toggle */}
            <button
              className="md:hidden w-9 h-9 rounded-xl bg-white/8 flex items-center justify-center text-slate-300 cursor-pointer"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              {mobileOpen ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>
        </div>

        {/* Mobile nav */}
        {mobileOpen && (
          <nav className="md:hidden mt-3 flex flex-wrap gap-2 pb-2">
            {visibleNav.map(n => {
              const Icon = n.icon;
              const active = tab === n.key;
              return (
                <button
                  key={n.key}
                  onClick={() => { setTab(n.key); setMobileOpen(false); }}
                  className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition cursor-pointer
                    ${active ? 'bg-teal-600/25 text-teal-300' : 'text-slate-400 hover:text-white hover:bg-white/8'}`}
                >
                  <Icon size={15} />
                  {n.label}
                </button>
              );
            })}
          </nav>
        )}
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-5 py-6">
        {renderPage()}
      </main>

      {/* Footer */}
      <footer className="text-center py-4 text-xs text-slate-500">
        <span>AI-Based Clinical image Diagnostic Assistant for Doctors</span>
        <span className="mx-2">&middot;</span>
        <span>&copy; Made by DHARSHAN KUMAR B (1DA23CS050)</span>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}

function AppRouter() {
  const { isLoggedIn } = useAuth();
  return isLoggedIn ? <Shell /> : <LoginPage />;
}
