import { useState, useRef, useEffect, useCallback } from 'react';
import { api } from '../api';
import GlassCard, { SectionTitle, Input, TextArea, Btn, Badge, StatusMsg, ResultPanel } from '../components/ui';
import { Image as ImageIcon, Upload, Save, Sparkles } from 'lucide-react';

/* ── colour per task type ── */
const TASK_COLORS = {
  fracture:            { box: '#ef4444', bg: 'rgba(239,68,68,0.18)', text: '#fca5a5' },
  tumor:               { box: '#f59e0b', bg: 'rgba(245,158,11,0.18)', text: '#fde68a' },
  kidney_stone:        { box: '#f97316', bg: 'rgba(249,115,22,0.18)', text: '#fdba74' },
  skin_classification: { box: '#14b8a6', bg: 'rgba(20,184,166,0.18)', text: '#5eead4' },
  default:             { box: '#6366f1', bg: 'rgba(99,102,241,0.18)', text: '#a5b4fc' },
};

function getTaskColor(task) {
  return TASK_COLORS[task] || TASK_COLORS.default;
}

export default function ImagePage() {
  const fileRef = useRef(null);
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [symptoms, setSymptoms] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [imgNatural, setImgNatural] = useState({ w: 0, h: 0 });

  // Store
  const [storePatient, setStorePatient] = useState('');
  const [storeDoctor, setStoreDoctor] = useState('');
  const [storeNotes, setStoreNotes] = useState('');
  const [storeStatus, setStoreStatus] = useState({ msg: '', err: false });

  /* ── draw detection boxes on canvas ── */
  const drawDetections = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !result?.detections?.length) {
      if (canvas) { const c = canvas.getContext('2d'); c && c.clearRect(0, 0, canvas.width, canvas.height); }
      return;
    }

    const elemRect = img.getBoundingClientRect();
    const natW = imgNatural.w || 1;
    const natH = imgNatural.h || 1;

    // compute the actual displayed image area inside object-contain
    const imgAspect = natW / natH;
    const elemAspect = elemRect.width / elemRect.height;
    let dispW, dispH, offX, offY;
    if (imgAspect > elemAspect) {
      dispW = elemRect.width; dispH = elemRect.width / imgAspect;
      offX = 0; offY = (elemRect.height - dispH) / 2;
    } else {
      dispH = elemRect.height; dispW = elemRect.height * imgAspect;
      offX = (elemRect.width - dispW) / 2; offY = 0;
    }

    canvas.width = elemRect.width;
    canvas.height = elemRect.height;
    canvas.style.width = elemRect.width + 'px';
    canvas.style.height = elemRect.height + 'px';

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const origW = result.image_width || natW;
    const origH = result.image_height || natH;
    const scaleX = dispW / origW;
    const scaleY = dispH / origH;
    const taskKey = result.routed_task || result.condition || '';
    const colors = getTaskColor(taskKey);

    result.detections.forEach((det) => {
      if (!det.bbox || det.bbox.length < 4) return;
      const [x1, y1, x2, y2] = det.bbox;
      const dx = offX + x1 * scaleX;
      const dy = offY + y1 * scaleY;
      const dw = (x2 - x1) * scaleX;
      const dh = (y2 - y1) * scaleY;

      // filled background
      ctx.fillStyle = colors.bg;
      ctx.fillRect(dx, dy, dw, dh);

      // border
      ctx.strokeStyle = colors.box;
      ctx.lineWidth = 2;
      ctx.setLineDash(det.is_estimated ? [6, 4] : []);
      ctx.strokeRect(dx, dy, dw, dh);

      // label
      const label = `${det.label}  ${(det.confidence * 100).toFixed(1)}%`;
      ctx.font = 'bold 12px Inter, system-ui, sans-serif';
      const tm = ctx.measureText(label);
      const lh = 20;
      const lx = dx;
      const ly = dy > lh + 4 ? dy - lh - 2 : dy;

      ctx.fillStyle = colors.box;
      ctx.fillRect(lx, ly, tm.width + 10, lh);
      ctx.fillStyle = '#fff';
      ctx.fillText(label, lx + 5, ly + 14);
    });

    ctx.setLineDash([]);
  }, [result, imgNatural]);

  useEffect(() => { drawDetections(); }, [drawDetections]);

  useEffect(() => {
    window.addEventListener('resize', drawDetections);
    return () => window.removeEventListener('resize', drawDetections);
  }, [drawDetections]);

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setPreview(URL.createObjectURL(file));
      setResult(null);
    }
  };

  const handleImgLoad = () => {
    const img = imgRef.current;
    if (img) {
      setImgNatural({ w: img.naturalWidth, h: img.naturalHeight });
      setTimeout(drawDetections, 50);
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

          {/* Drop zone with detection overlay */}
          <div
            onClick={() => !result && fileRef.current?.click()}
            className="border-2 border-dashed border-white/15 rounded-2xl p-4 text-center cursor-pointer hover:border-teal-500/40 hover:bg-white/5 transition-all group relative"
          >
            {preview ? (
              <div className="relative inline-block w-full">
                <img
                  ref={imgRef}
                  src={preview}
                  alt="Preview"
                  className="max-h-64 mx-auto rounded-xl object-contain"
                  onLoad={handleImgLoad}
                />
                <canvas
                  ref={canvasRef}
                  className="absolute top-0 left-0 w-full h-full pointer-events-none"
                />
                {/* Model task badge */}
                {result && !result.error && (
                  <div className="absolute top-2 left-2 flex flex-col gap-1">
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                      style={{
                        backgroundColor: getTaskColor(result.routed_task || '').bg,
                        color: getTaskColor(result.routed_task || '').text,
                        border: `1px solid ${getTaskColor(result.routed_task || '').box}40`,
                      }}>
                      {(result.routed_task || result.condition || '').replace(/_/g, ' ').toUpperCase()}
                    </span>
                    {result.model_name && (
                      <span className="text-[9px] px-2 py-0.5 rounded-full bg-white/10 text-slate-400">
                        {result.model_name}
                      </span>
                    )}
                  </div>
                )}
              </div>
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
                  <span className="font-semibold text-white">{result.condition?.replace(/_/g, ' ')}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Confidence</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all" style={{
                        width: `${(result.confidence || 0) * 100}%`,
                        backgroundColor: getTaskColor(result.routed_task || '').box,
                      }} />
                    </div>
                    <span className="text-white text-xs">{(Number(result.confidence || 0) * 100).toFixed(1)}%</span>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-400">Risk Level</span>
                  <Badge level={result.risk_level || 'low'} />
                </div>

                {/* Detection breakdown */}
                {result.detections?.length > 0 && (
                  <ResultPanel>
                    <p className="text-xs text-slate-400 mb-2">Detections ({result.detections.length})</p>
                    <div className="space-y-1.5">
                      {result.detections.map((det, i) => {
                        const colors = getTaskColor(result.routed_task || '');
                        return (
                          <div key={i} className="flex items-center justify-between gap-2 py-1 px-2 rounded-lg" style={{ backgroundColor: colors.bg }}>
                            <div className="flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colors.box }} />
                              <span className="text-xs font-medium" style={{ color: colors.text }}>{det.label?.replace(/_/g, ' ')}</span>
                              {det.is_estimated && <span className="text-[9px] text-slate-500 italic">estimated</span>}
                            </div>
                            <span className="text-xs text-white font-mono">{(det.confidence * 100).toFixed(1)}%</span>
                          </div>
                        );
                      })}
                    </div>
                  </ResultPanel>
                )}

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
