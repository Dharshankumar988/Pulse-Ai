import { useState, useEffect } from 'react';
import { api } from '../api';
import GlassCard, { SectionTitle, Btn } from '../components/ui';
import { Users, RefreshCw, History, Search } from 'lucide-react';

export default function PatientsPage() {
  const [patients, setPatients] = useState([]);
  const [nameSearch, setNameSearch] = useState('');
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [selectedPatientName, setSelectedPatientName] = useState('');
  const [history, setHistory] = useState([]);
  const [histOrder, setHistOrder] = useState('desc');

  const removePatient = async (patient) => {
    const ok = window.confirm(`Delete ${patient.full_name || 'this patient'} and all associated records?`);
    if (!ok) return;

    try {
      await api(`/patient-management/patients/${patient.id}`, { method: 'DELETE' });
      setPatients(prev => prev.filter(item => item.id !== patient.id));
      if (selectedPatientId === patient.id) {
        setSelectedPatientId('');
        setSelectedPatientName('');
        setHistory([]);
      }
    } catch {
      window.alert('Unable to delete patient. Please try again.');
    }
  };

  const loadPatients = async (searchText = '') => {
    try {
      const query = searchText.trim() ? `?name=${encodeURIComponent(searchText.trim())}` : '';
      const res = await api(`/patient-management/patients${query}`);
      setPatients(res.data || []);
    } catch (err) {
      setPatients([]);
    }
  };

  const loadHistory = async (patientId) => {
    try {
      if (!patientId) {
        setHistory([]);
        return;
      }
      const res = await api(`/patient-management/patients/${patientId}/history?order=${histOrder}`);
      setHistory(res.data || []);
    } catch (err) {
      setHistory([]);
    }
  };

  useEffect(() => { loadPatients(); }, []);

  useEffect(() => {
    const timer = setTimeout(() => loadPatients(nameSearch), 250);
    return () => clearTimeout(timer);
  }, [nameSearch]);

  useEffect(() => {
    if (selectedPatientId) loadHistory(selectedPatientId);
  }, [selectedPatientId, histOrder]);

  const formatTs = (value) => {
    if (!value) return '—';
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return String(value);
    return dt.toLocaleString();
  };

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionTitle icon={Users}>My Patients</SectionTitle>

      <GlassCard>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-white">Patients List</h3>
          <Btn variant="ghost" onClick={() => loadPatients(nameSearch)}>
            <span className="flex items-center gap-1"><RefreshCw size={13}/>Refresh</span>
          </Btn>
        </div>
        <div className="mb-3">
          <label className="text-xs text-slate-400 mb-1 block">Search by patient name</label>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              value={nameSearch}
              onChange={e => setNameSearch(e.target.value)}
              placeholder="Type a name..."
              className="glass-input w-full rounded-xl pl-9 pr-3 py-2.5 text-sm text-white placeholder:text-slate-500"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-white/10">
                <th className="pb-2 pr-3">Name</th>
                <th className="pb-2 pr-3">DOB</th>
                <th className="pb-2 pr-3">Email</th>
                <th className="pb-2 pr-3">Phone</th>
                <th className="pb-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {patients.length === 0 && (
                <tr><td colSpan={5} className="py-6 text-center text-slate-500">No patients found.</td></tr>
              )}
              {patients.map(p => (
                <tr
                  key={p.id}
                  className={`border-b border-white/5 hover:bg-white/5 transition-colors cursor-pointer ${selectedPatientId === p.id ? 'bg-teal-600/10' : ''}`}
                  onClick={() => {
                    setSelectedPatientId(p.id);
                    setSelectedPatientName(p.full_name || 'Selected Patient');
                  }}
                >
                  <td className="py-2.5 pr-3 text-white">{p.full_name}</td>
                  <td className="py-2.5 pr-3 text-slate-300">{p.date_of_birth || '—'}</td>
                  <td className="py-2.5 pr-3 text-slate-300">{p.email || '—'}</td>
                  <td className="py-2.5 pr-3 text-slate-300">{p.phone || '—'}</td>
                  <td className="py-2.5 text-right">
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        removePatient(p);
                      }}
                      className="px-2.5 py-1 rounded-lg text-xs border border-red-400/30 bg-red-500/10 text-red-200 hover:bg-red-500/20 transition"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GlassCard>

      <GlassCard>
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <History size={15} className="text-amber-400" />
          {selectedPatientName ? `${selectedPatientName} — Chat & Clinical History` : 'Patient History'}
        </h3>

        <div className="flex gap-3 items-end flex-wrap mb-3">
          <label className="flex flex-col gap-1.5 text-sm text-slate-300">
            Order
            <select
              value={histOrder}
              onChange={e => setHistOrder(e.target.value)}
              className="glass-input rounded-xl px-3 py-2.5 text-sm text-white"
            >
              <option value="desc">Newest first</option>
              <option value="asc">Oldest first</option>
            </select>
          </label>
          <Btn onClick={() => loadHistory(selectedPatientId)}>Fetch</Btn>
        </div>

        {!selectedPatientId && <p className="text-xs text-slate-500">Click a patient above to load history instantly.</p>}
        {selectedPatientId && history.length === 0 && <p className="text-xs text-slate-500">No history entries found.</p>}

        {history.length > 0 && (
          <div className="mt-2 space-y-3">
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
                      <p className="md:col-span-2"><span className="text-slate-400">Notes:</span> <span className="text-white">{data.notes || '—'}</span></p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                      <p><span className="text-slate-400">Diagnosis:</span> <span className="text-white">{data.diagnosis || '—'}</span></p>
                      <p><span className="text-slate-400">Status:</span> <span className="text-white">{data.status || '—'}</span></p>
                      <p className="md:col-span-2"><span className="text-slate-400">Notes:</span> <span className="text-white">{data.notes || '—'}</span></p>
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
