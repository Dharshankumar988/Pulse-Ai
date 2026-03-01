import { useState } from 'react';
import { api } from '../api';
import GlassCard, { SectionTitle, Btn, StatusMsg } from '../components/ui';
import { ShieldCheck, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';

export default function AdminPage() {
  const [doctors, setDoctors] = useState([]);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const res = await api('/admin/doctors/pending');
      setDoctors(res.data || []);
      setStatus(`${(res.data || []).length} pending doctor(s)`);
    } catch (err) { setStatus(err.message); }
    finally { setLoading(false); }
  };

  const handleAction = async (id, action) => {
    try {
      await api(`/admin/doctors/${id}/${action}`, { method: 'POST' });
      setStatus(`${action}d doctor ${id.slice(0, 8)}…`);
      refresh();
    } catch (err) { setStatus(err.message); }
  };

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionTitle icon={ShieldCheck}>Admin Dashboard</SectionTitle>

      <GlassCard>
        <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
          <p className="text-sm text-slate-400">Manage pending doctor approvals</p>
          <Btn variant="secondary" onClick={refresh} disabled={loading}>
            <span className="flex items-center gap-2">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              Refresh
            </span>
          </Btn>
        </div>

        <StatusMsg msg={status} />

        <div className="overflow-x-auto mt-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-white/10">
                <th className="pb-2 pr-3">Name</th>
                <th className="pb-2 pr-3">Email</th>
                <th className="pb-2 pr-3">Specialty</th>
                <th className="pb-2 pr-3">Status</th>
                <th className="pb-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {doctors.length === 0 && (
                <tr><td colSpan={5} className="py-6 text-center text-slate-500">No pending doctors. Click Refresh.</td></tr>
              )}
              {doctors.map(d => (
                <tr key={d.user_id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                  <td className="py-3 pr-3 text-white">{d.full_name}</td>
                  <td className="py-3 pr-3 text-slate-300">{d.email}</td>
                  <td className="py-3 pr-3 text-slate-300">{d.specialty}</td>
                  <td className="py-3 pr-3">
                    <span className="bg-amber-500/15 text-amber-400 px-2 py-0.5 rounded-full text-xs">{d.status}</span>
                  </td>
                  <td className="py-3 flex gap-2">
                    <button onClick={() => handleAction(d.user_id, 'approve')}
                      className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30 transition cursor-pointer">
                      <CheckCircle2 size={13} /> Approve
                    </button>
                    <button onClick={() => handleAction(d.user_id, 'reject')}
                      className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg bg-red-600/20 text-red-400 hover:bg-red-600/30 transition cursor-pointer">
                      <XCircle size={13} /> Reject
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>
    </div>
  );
}
