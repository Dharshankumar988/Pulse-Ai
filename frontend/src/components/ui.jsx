import { Activity } from 'lucide-react';

export default function GlassCard({ children, className = '', glow = false }) {
  return (
    <div className={`glass rounded-2xl p-5 ${glow ? 'glow-sm' : ''} ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({ icon: Icon = Activity, children }) {
  return (
    <h2 className="flex items-center gap-2 text-xl font-bold text-white mb-4">
      <Icon size={22} className="text-teal-400" />
      {children}
    </h2>
  );
}

export function StatusMsg({ msg, isError }) {
  if (!msg) return null;
  return (
    <p className={`text-xs mt-2 ${isError ? 'text-red-400' : 'text-slate-400'}`}>
      {msg}
    </p>
  );
}

export function Badge({ level }) {
  const map = {
    low: 'bg-emerald-500/15 text-emerald-400',
    medium: 'bg-amber-500/15 text-amber-400',
    high: 'bg-red-500/15 text-red-400',
    critical: 'bg-red-500/25 text-red-300',
    ok: 'bg-emerald-500/15 text-emerald-400',
  };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${map[level] || map.low}`}>
      {level}
    </span>
  );
}

export function Input({ label, className = '', ...props }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm text-slate-300">
      {label}
      <input
        className={`glass-input rounded-xl px-3.5 py-2.5 text-sm text-white placeholder:text-slate-500 transition-all ${className}`}
        {...props}
      />
    </label>
  );
}

export function TextArea({ label, className = '', ...props }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm text-slate-300">
      {label}
      <textarea
        className={`glass-input rounded-xl px-3.5 py-2.5 text-sm text-white placeholder:text-slate-500 resize-y min-h-[100px] transition-all ${className}`}
        {...props}
      />
    </label>
  );
}

export function Btn({ children, variant = 'primary', className = '', ...props }) {
  const base = 'rounded-xl px-4 py-2.5 text-sm font-semibold transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed';
  const variants = {
    primary: 'bg-teal-600 hover:bg-teal-500 text-white glow-sm',
    secondary: 'bg-white/10 hover:bg-white/15 text-slate-200 border border-white/10',
    danger: 'bg-red-600 hover:bg-red-500 text-white',
    ghost: 'bg-transparent hover:bg-white/5 text-slate-300 border border-white/10',
  };
  return (
    <button className={`${base} ${variants[variant] || variants.primary} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function ResultPanel({ children }) {
  return (
    <div className="bg-black/20 backdrop-blur-sm border border-white/10 rounded-xl p-4 mt-3 text-sm">
      {children}
    </div>
  );
}
