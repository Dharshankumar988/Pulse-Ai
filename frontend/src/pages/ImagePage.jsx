import { useState, useRef } from 'react';
import { api } from '../api';
import GlassCard, { SectionTitle, Input, TextArea, Btn, Badge, StatusMsg, ResultPanel } from '../components/ui';
import { Image as ImageIcon, Upload, Save, Sparkles } from 'lucide-react';

export default function ImagePage() {
  const fileRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [symptoms, setSymptoms] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // Store
  const [storePatient, setStorePatient] = useState('');
  const [storeDoctor, setStoreDoctor] = useState('');
  const [storeNotes, setStoreNotes] = useState('');
  const [storeStatus, setStoreStatus] = useState({ msg: '', err: false });

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setPreview(URL.createObjectURL(file));
    }
  };

  const analyze = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      if (symptoms.trim()) fd.append('symptoms', symptoms.trim());
      const res = await api('/multimodal/analyze', { method: 'POST', body: fd });
      setResult(res);
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setLoading(false);
    }
  };

  const store = async () => {
    if (!result || result.error) return setStoreStatus({ msg: 'Run analysis first', err: true });
    if (!storePatient || !storeDoctor) return setStoreStatus({ msg: 'Patient & Doctor ID required', err: true });

    const confidence = Number(result.confidence || 0);
    let severity = 'moderate';
    if (confidence >= 0.85) severity = 'critical';
    else if (confidence >= 0.65) severity = 'high';
    else if (confidence < 0.4) severity = 'low';

    const payload = {
      patient_id: storePatient,
      doctor_id: storeDoctor,
      disease: result.condition || 'general_non_specific_finding',
      probability: Math.max(0, Math.min(1, confidence)),
      severity,
      risk: result.risk_level || 'medium',
      uncertainty: Math.max(0, Math.min(1, 1 - confidence)),
      recommendations: result.recommendation || {},
      follow_up_questions: [],
      sources: { frontend: 'manual-store', notes: result.notes || '' },
      notes: storeNotes || null,
    };

    try {
      const res = await api('/patient-management/analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setStoreStatus({ msg: `Stored: ${res.data?.id || 'ok'}`, err: false });
    } catch (err) {
      setStoreStatus({ msg: err.message, err: true });
    }
  };

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionTitle icon={ImageIcon}>Image Analysis</SectionTitle>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Upload */}
        <GlassCard>
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Upload size={15} className="text-teal-400" /> Upload Medical Image
          </h3>

          {/* Drop zone */}
          <div
            onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed border-white/15 rounded-2xl p-8 text-center cursor-pointer hover:border-teal-500/40 hover:bg-white/5 transition-all group"
          >
            {preview ? (
              <img src={preview} alt="Preview" className="max-h-48 mx-auto rounded-xl object-contain" />
            ) : (
              <div className="space-y-2">
                <Upload size={32} className="mx-auto text-slate-500 group-hover:text-teal-400 transition" />
                <p className="text-sm text-slate-400">Click to select an image</p>
                <p className="text-xs text-slate-500">PNG, JPG, DICOM supported</p>
              </div>
            )}
          </div>
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />

          <div className="mt-4">
            <TextArea label="Optional Symptoms" placeholder="Provide additional symptom context…" value={symptoms} onChange={e => setSymptoms(e.target.value)} />
          </div>

          <Btn className="w-full mt-4" disabled={loading} onClick={analyze}>
            <span className="flex items-center justify-center gap-2">
              <Sparkles size={16} />
              {loading ? 'Analyzing…' : 'Analyze Image'}
            </span>
          </Btn>
        </GlassCard>

        {/* Results */}
        <div className="space-y-4">
          <GlassCard>
            <h3 className="text-sm font-semibold text-white mb-3">Analysis Result</h3>
            {!result ? (
              <p className="text-sm text-slate-500">Upload and analyze an image to see results here</p>
            ) : result.error ? (
              <p className="text-sm text-red-400">{result.error}</p>
            ) : (
              <div className="space-y-3 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Condition</span>
                  <span className="font-semibold text-white">{result.condition}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Confidence</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                      <div className="h-full bg-teal-500 rounded-full transition-all" style={{ width: `${(result.confidence || 0) * 100}%` }} />
                    </div>
                    <span className="text-white text-xs">{(Number(result.confidence || 0) * 100).toFixed(1)}%</span>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Risk Level</span>
                  <Badge level={result.risk_level || 'low'} />
                </div>
                {result.recommendation && (
                  <ResultPanel>
                    <p className="text-xs text-slate-400 mb-1">Recommendation</p>
                    <pre className="whitespace-pre-wrap break-words text-xs text-slate-300">
                      {typeof result.recommendation === 'string' ? result.recommendation : JSON.stringify(result.recommendation, null, 2)}
                    </pre>
                  </ResultPanel>
                )}
                {result.notes && <p className="text-xs text-slate-400 italic mt-2">{result.notes}</p>}
              </div>
            )}
          </GlassCard>

          {/* Store */}
          <GlassCard>
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Save size={15} className="text-amber-400" /> Store Analysis
            </h3>
            <div className="space-y-3">
              <Input label="Patient ID" value={storePatient} onChange={e => setStorePatient(e.target.value)} />
              <Input label="Doctor ID" value={storeDoctor} onChange={e => setStoreDoctor(e.target.value)} />
              <TextArea label="Notes" placeholder="Clinical notes…" value={storeNotes} onChange={e => setStoreNotes(e.target.value)} />
            </div>
            <Btn variant="secondary" className="w-full mt-3" onClick={store}>Store Result</Btn>
            <StatusMsg msg={storeStatus.msg} isError={storeStatus.err} />
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
