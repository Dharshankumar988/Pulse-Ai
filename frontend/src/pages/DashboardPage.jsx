import { useState, useEffect } from 'react';
import { api } from '../api';
import GlassCard, { SectionTitle, Btn } from '../components/ui';
import { LayoutDashboard, HeartPulse, Users, History } from 'lucide-react';

export default function DashboardPage() {
  const [health, setHealth] = useState(null);
  const [patientsCount, setPatientsCount] = useState(null);
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [history, setHistory] = useState([]);

  useEffect(() => {
    api('/health').then(setHealth).catch(() => setHealth({ status: 'unreachable' }));
    api('/patient-management/patients')
      .then(r => {
        const list = r.data || [];
        setPatients(list);
        setPatientsCount(r.count ?? list.length ?? 0);
      })
      .catch(() => {
        setPatientsCount('—');
        setPatients([]);
      });
  }, []);

  const loadHistory = async () => {
    if (!selectedPatientId.trim()) return;
    try {
      const res = await api(`/patient-management/patients/${selectedPatientId.trim()}/history?order=desc`);
      setHistory((res.data || []).slice(0, 5));
    } catch (err) { setHistory([]); }
  };

  useEffect(() => {
    if (!selectedPatientId) {
      setHistory([]);
      return;
    }
    loadHistory();
  }, [selectedPatientId]);

  const formatTs = (value) => {
    if (!value) return '—';
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return String(value);
    return dt.toLocaleString();
  };

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionTitle icon={LayoutDashboard}>Dashboard</SectionTitle>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* System health */}
        <GlassCard glow>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-teal-600/20 flex items-center justify-center">
              <HeartPulse size={20} className="text-teal-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">System Status</p>
              <p className="text-lg font-bold text-white">{health?.status || 'Loading…'}</p>
            </div>
          </div>
        </GlassCard>

        {/* Patient count */}
        <GlassCard>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600/20 flex items-center justify-center">
              <Users size={20} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">Total Patients</p>
              <p className="text-lg font-bold text-white">{patientsCount ?? '…'}</p>
            </div>
          </div>
        </GlassCard>

        {/* Quick pulse */}
        <GlassCard>
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-xl bg-amber-600/20 flex items-center justify-center">
              <History size={20} className="text-amber-400" />
            </div>
            <div>
              <p className="text-xs text-slate-400">Uptime</p>
              <p className="text-lg font-bold text-white">Active</p>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Recent history */}
      <GlassCard>
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <History size={16} className="text-teal-400" /> Recent Patient History
        </h3>
        <div className="flex gap-3 items-end flex-wrap">
          <label className="flex-1 min-w-55 flex flex-col gap-1.5 text-sm text-slate-300">
            Patient Name
            <select
              value={selectedPatientId}
              onChange={e => setSelectedPatientId(e.target.value)}
              className="glass-input rounded-xl px-3 py-2.5 text-sm text-white"
            >
              <option value="">Select patient</option>
              {patients.map(p => (
                <option key={p.id} value={p.id}>{p.full_name}</option>
              ))}
            </select>
          </label>
          <Btn onClick={loadHistory}>Load</Btn>
        </div>
        {!selectedPatientId && <p className="text-xs text-slate-500 mt-3">Select a patient to view recent history.</p>}
        {selectedPatientId && history.length === 0 && <p className="text-xs text-slate-500 mt-3">No recent entries found.</p>}
        {history.length > 0 && (
          <div className="mt-4 space-y-3">
            {history.map((entry, index) => {
              const data = entry.data || {};
              const isAnalysis = entry.entry_type === 'analysis';
              return (
                <div key={`${entry.timestamp || 'ts'}-${index}`} className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <p className="text-xs uppercase tracking-wide text-teal-300">{isAnalysis ? 'Analysis' : 'Record'}</p>
                    <p className="text-xs text-slate-400">{formatTs(entry.timestamp)}</p>
                  </div>
                  {isAnalysis ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                      <p><span className="text-slate-400">Condition:</span> <span className="text-white">{data.disease || '—'}</span></p>
                      <p><span className="text-slate-400">Probability:</span> <span className="text-white">{typeof data.probability === 'number' ? `${(data.probability * 100).toFixed(1)}%` : '—'}</span></p>
                      <p><span className="text-slate-400">Risk:</span> <span className="text-white">{data.risk || '—'}</span></p>
                      <p><span className="text-slate-400">Primary drug:</span> <span className="text-white">{data.recommendations?.primary_drug || data.recommendations?.drugs?.[0] || '—'}</span></p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                      <p><span className="text-slate-400">Diagnosis:</span> <span className="text-white">{data.diagnosis || '—'}</span></p>
                      <p><span className="text-slate-400">Status:</span> <span className="text-white">{data.status || '—'}</span></p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </GlassCard>
    </div>
  );
}
