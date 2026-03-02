import { useState, useEffect } from 'react';
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
  AlertTriangle,
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
  const [showAccessPolicy, setShowAccessPolicy] = useState(false);

  // Show access-policy popup once per login session
  useEffect(() => {
    const dismissed = sessionStorage.getItem('pulseAccessPolicyDismissed');
    if (!dismissed) setShowAccessPolicy(true);
  }, []);

  const dismissPolicy = () => {
    setShowAccessPolicy(false);
    sessionStorage.setItem('pulseAccessPolicyDismissed', '1');
  };

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
      {/* Access-policy popup */}
      {showAccessPolicy && (
        <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md glass-strong rounded-3xl p-8 text-center space-y-5 animate-fade-up shadow-2xl border border-amber-400/20">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-amber-500/15 border border-amber-400/30 mx-auto">
              <AlertTriangle size={30} className="text-amber-400" />
            </div>
            <h2 className="text-xl font-bold text-white">Access Policy</h2>
            <p className="text-slate-300 text-sm leading-relaxed">
              This assistant is intended for <span className="text-amber-300 font-semibold">verified physicians / clinicians only</span>; non-verified users must not use it.
            </p>
            <button
              onClick={dismissPolicy}
              className="mt-2 px-6 py-2.5 rounded-xl bg-teal-600/30 hover:bg-teal-600/50 text-teal-200 text-sm font-semibold border border-teal-400/30 transition cursor-pointer"
            >
              I understand &mdash; Continue
            </button>
          </div>
        </div>
      )}

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
