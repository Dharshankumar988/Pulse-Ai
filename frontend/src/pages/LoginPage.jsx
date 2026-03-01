import { useState } from 'react';
import { useAuth } from '../AuthContext';
import { api } from '../api';
import { Input, Btn, StatusMsg } from '../components/ui';
import { Activity, LogIn, UserPlus, CheckCircle } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const [mode, setMode] = useState('login'); // 'login' | 'register' | 'registered'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState('doctor'); // 'doctor' | 'admin'
  const [specialty, setSpecialty] = useState('');
  const [phone, setPhone] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setLoading(true);
    setStatus('');
    try {
      const res = await api('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      }, false);
      login(res.access_token, res.user);
    } catch (err) {
      setStatus(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    setLoading(true);
    setStatus('');
    try {
      if (!fullName.trim()) throw new Error('Full name is required');
      if (role === 'doctor' && !specialty.trim()) throw new Error('Specialty is required for doctors');
      const body = { email, password, full_name: fullName, role, phone: phone || null };
      if (role === 'doctor') body.specialty = specialty;
      await api('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }, false);
      setMode('registered');
    } catch (err) {
      setStatus(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Success screen after registration
  if (mode === 'registered') {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="w-full max-w-md animate-fade-up text-center">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-emerald-600/20 border border-emerald-500/30 mb-5">
            <CheckCircle size={36} className="text-emerald-400" />
          </div>
          <h1 className="text-3xl font-extrabold text-white mb-3">Registration Submitted</h1>
          <p className="text-slate-400 text-sm mb-6">
            Your account has been created. An admin will review and approve your profile before you can sign in.
          </p>
          <div className="glass-strong rounded-3xl p-6">
            <p className="text-sm text-slate-300 mb-1">Registered as</p>
            <p className="text-white font-semibold">{email}</p>
            <p className="text-xs text-amber-400 mt-2">Status: Pending Approval</p>
          </div>
          <button
            onClick={() => { setMode('login'); setStatus(''); }}
            className="mt-6 text-teal-400 hover:text-teal-300 text-sm font-medium transition cursor-pointer"
          >
            ← Back to Sign In
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-md animate-fade-up">
        {/* Logo + Hero */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-teal-600/20 border border-teal-500/30 mb-5 glow-teal">
            <Activity size={36} className="text-teal-400 animate-pulse-ring" />
          </div>
          <h1 className="text-4xl font-extrabold text-white tracking-tight">
            Pulse
          </h1>
          <p className="text-slate-400 mt-2 text-sm">
            AI-Based Clinical image Diagnostic Assistant for Doctors
          </p>
        </div>

        {/* Glass card */}
        <div className="glass-strong rounded-3xl p-8 space-y-5">

          {/* Mode toggle */}
          <div className="flex rounded-xl bg-white/8 p-1">
            <button
              onClick={() => { setMode('login'); setStatus(''); }}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                mode === 'login' ? 'bg-teal-600/30 text-teal-300 shadow-sm' : 'text-slate-400 hover:text-white'
              }`}
            >
              <LogIn size={15} /> Sign In
            </button>
            <button
              onClick={() => { setMode('register'); setStatus(''); }}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
                mode === 'register' ? 'bg-teal-600/30 text-teal-300 shadow-sm' : 'text-slate-400 hover:text-white'
              }`}
            >
              <UserPlus size={15} /> Register
            </button>
          </div>

          {/* Common fields */}
          <Input label="Email" type="email" placeholder="doctor@hospital.com" value={email}
            onChange={e => setEmail(e.target.value)} />
          <Input label="Password" type="password" placeholder="••••••••" value={password}
            onChange={e => setPassword(e.target.value)} />

          {/* Register-only fields */}
          {mode === 'register' && (
            <>
              <Input label="Full Name" placeholder="Dr. Jane Smith" value={fullName}
                onChange={e => setFullName(e.target.value)} />
              <Input label="Specialty" placeholder="Cardiology, Radiology, etc." value={specialty}
                onChange={e => setSpecialty(e.target.value)} />
              <Input label="Phone (optional)" placeholder="+1 555 123 4567" value={phone}
                onChange={e => setPhone(e.target.value)} />
            </>
          )}

          <Btn className="w-full" disabled={loading}
            onClick={mode === 'login' ? handleLogin : handleRegister}>
            {loading
              ? (mode === 'login' ? 'Signing in…' : 'Registering…')
              : (mode === 'login' ? 'Sign In' : 'Register as Doctor')
            }
          </Btn>

          <StatusMsg msg={status} isError />
        </div>

        <p className="text-center text-slate-500 text-xs mt-6">
          {mode === 'login'
            ? 'Admin accounts can sign in directly. Doctors need admin approval first.'
            : 'After registration, an admin must approve your account before you can sign in.'
          }
        </p>
      </div>
    </div>
  );
}
