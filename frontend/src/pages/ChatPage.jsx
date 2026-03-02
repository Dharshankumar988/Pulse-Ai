import { useState, useRef, useEffect } from 'react';
import { api } from '../api';
import GlassCard, { SectionTitle, Badge, StatusMsg, Btn, Input } from '../components/ui';
import { MessageCircle, Send, Sparkles, Bot, User, Paperclip, X } from 'lucide-react';

function buildPrompts(result, hasSymptoms, hasImage) {
  const prompts = [];
  if (!hasSymptoms) {
    prompts.push('When did your symptoms start?');
    prompts.push('Are symptoms improving, worsening, or unchanged?');
  }
  if (!hasImage) {
    prompts.push('If possible, upload a relevant image to improve confidence.');
    prompts.push('Use a clear, well-lit close-up image.');
  }
  if (result?.risk_level === 'high') {
    prompts.push('Are symptoms worsening rapidly?');
    prompts.push('Any red flags like bleeding or severe breathlessness?');
  }
  const cond = String(result?.condition || '').toLowerCase();
  if (cond.includes('fracture')) prompts.push('Do you have swelling or inability to move the limb?');
  if (cond.includes('tumor')) prompts.push('Any unexplained weight loss?');
  if (cond.includes('kidney')) prompts.push('Any flank pain or blood in urine?');
  if ((result?.confidence || 0) < 0.7) {
    prompts.push('Can you upload a clearer image or different angle?');
    prompts.push('Add more symptom detail to reduce uncertainty.');
  }
  return [...new Set(prompts)].slice(0, 6);
}

function DetectionOverlayImage({ image, data, onOpenImage, mode = 'inline' }) {
  const detections = data?.detections || [];
  const imageWidth = Number(data?.image_width || 0);
  const imageHeight = Number(data?.image_height || 0);
  const condition = String(data?.condition || '').trim();
  const confidencePct = Math.round(Number(data?.confidence || 0) * 100);
  const analysisLabel = condition ? `Analyzed ${condition} ${confidencePct}%` : '';
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 });

  if (!image) return null;

  const effectiveWidth = imageWidth || naturalSize.width;
  const effectiveHeight = imageHeight || naturalSize.height;

  const overlayDetections = detections.length
    ? detections
    : [{ label: condition || 'suspected_finding', confidence: Number(data?.confidence || 0), bbox: [0.2, 0.2, 0.8, 0.8], is_estimated: true }];

  const getBoxPercent = (bbox) => {
    if (!bbox || bbox.length !== 4) return null;
    const [x1, y1, x2, y2] = bbox.map(Number);
    if ([x1, y1, x2, y2].some(value => Number.isNaN(value))) return null;

    const maxCoord = Math.max(x1, y1, x2, y2);
    const isNormalized = maxCoord <= 1.2;

    if (isNormalized) {
      return {
        left: `${Math.max(0, Math.min(100, x1 * 100))}%`,
        top: `${Math.max(0, Math.min(100, y1 * 100))}%`,
        width: `${Math.max(2, Math.min(100, (x2 - x1) * 100))}%`,
        height: `${Math.max(2, Math.min(100, (y2 - y1) * 100))}%`,
      };
    }

    if (!effectiveWidth || !effectiveHeight) return null;
    return {
      left: `${Math.max(0, Math.min(100, (x1 / effectiveWidth) * 100))}%`,
      top: `${Math.max(0, Math.min(100, (y1 / effectiveHeight) * 100))}%`,
      width: `${Math.max(2, Math.min(100, ((x2 - x1) / effectiveWidth) * 100))}%`,
      height: `${Math.max(2, Math.min(100, ((y2 - y1) / effectiveHeight) * 100))}%`,
    };
  };

  return (
    <div className="relative inline-block max-w-full rounded-lg overflow-hidden border border-white/10">
      <img
        src={image}
        alt="Analyzed"
        className={mode === 'modal' ? 'max-h-none rounded-lg' : 'max-h-56 rounded-lg cursor-zoom-in'}
        onLoad={(event) => {
          const target = event.currentTarget;
          setNaturalSize({ width: target.naturalWidth || 0, height: target.naturalHeight || 0 });
        }}
        onClick={() => onOpenImage?.(image, 'Analyzed image', data)}
      />
      {analysisLabel && (
        <div className="absolute left-2 top-2 px-2 py-1 text-[11px] font-medium bg-black/70 text-amber-300 rounded border border-amber-400/40">
          {analysisLabel}
        </div>
      )}
      {overlayDetections.map((d, index) => {
        const box = getBoxPercent(d?.bbox);
        if (!box) return null;
        return (
          <div
            key={`${d.label}-${index}`}
            className="absolute border-2 border-amber-400 rounded-sm"
            style={box}
          >
            <div className="absolute -top-6 left-0 px-1.5 py-0.5 text-[10px] bg-amber-500/90 text-black rounded">
              {d.label} {(Number(d.confidence || 0) * 100).toFixed(0)}%
            </div>
          </div>
        );
      })}
    </div>
  );
}

function historyToChatMessages(historyEntries) {
  const ordered = [...(historyEntries || [])].reverse();
  const messages = [];

  for (const entry of ordered.slice(-10)) {
    const data = entry?.data || {};
    if (entry?.entry_type === 'analysis') {
      const notes = String(data.notes || '').trim();
      if (notes) {
        messages.push({ role: 'user', text: `Previous note: ${notes}` });
      }
      messages.push({
        role: 'bot',
        data: {
          condition: data.disease || data.condition || '—',
          confidence: Number(data.probability ?? data.confidence ?? 0),
          risk_level: data.risk || data.risk_level || 'medium',
          recommendation: data.recommendations || data.recommendation || {},
          follow_up_questions: data.follow_up_questions || [],
        },
      });
      continue;
    }

    const diagnosis = data.diagnosis || data.condition || 'previous injury';
    const status = data.status ? ` | Status: ${data.status}` : '';
    const notes = data.notes ? ` | Notes: ${data.notes}` : '';
    messages.push({ role: 'user', text: `Previous injury: ${diagnosis}${status}${notes}` });
  }

  return messages;
}

export default function ChatPage() {
  const [chatMode, setChatMode] = useState('quick');
  const [continueFromHistory, setContinueFromHistory] = useState(true);
  const [symptoms, setSymptoms] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [prompts, setPrompts] = useState(buildPrompts(null, false, false));
  const [isDragging, setIsDragging] = useState(false);
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [assistantStatus, setAssistantStatus] = useState({ msg: '', err: false });
  const [newPatient, setNewPatient] = useState({ full_name: '', date_of_birth: '', email: '', phone: '' });
  const [patientHistory, setPatientHistory] = useState([]);
  const [isCreatingPatient, setIsCreatingPatient] = useState(false);
  const [popup, setPopup] = useState({ open: false, text: '', error: false });
  const [imageModal, setImageModal] = useState({ open: false, src: '', alt: '', zoom: 1, analysisData: null });
  const messagesContainerRef = useRef(null);
  const fileRef = useRef(null);
  const dragDepthRef = useRef(0);
  const messageImageUrlsRef = useRef(new Set());
  const selectedPatientIdRef = useRef('');
  const historyRequestIdRef = useRef(0);
  const suppressNextAutoScrollRef = useRef(true);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, []);

  useEffect(() => {
    selectedPatientIdRef.current = selectedPatientId;
  }, [selectedPatientId]);

  useEffect(() => {
    api('/patient-management/patients')
      .then(res => setPatients(res.data || []))
      .catch(() => setPatients([]));
  }, []);

  useEffect(() => {
    const messageImageUrls = messageImageUrlsRef.current;
    return () => {
      messageImageUrls.forEach((url) => {
        if (String(url).startsWith('blob:')) {
          URL.revokeObjectURL(url);
        }
      });
      messageImageUrls.clear();
    };
  }, []);

  const showPopup = (text, error = false) => {
    setPopup({ open: true, text, error });
    setTimeout(() => setPopup({ open: false, text: '', error: false }), 2400);
  };

  const openImageModal = (src, alt = 'Image', analysisData = null) => {
    if (!src) return;
    setImageModal({ open: true, src, alt, zoom: 1, analysisData });
  };

  const closeImageModal = () => {
    setImageModal({ open: false, src: '', alt: '', zoom: 1, analysisData: null });
  };

  const setZoom = (nextZoom) => {
    setImageModal(prev => ({ ...prev, zoom: Math.max(0.5, Math.min(4, nextZoom)) }));
  };

  const zoomIn = () => setImageModal(prev => ({ ...prev, zoom: Math.min(4, Number((prev.zoom + 0.25).toFixed(2)) ) }));
  const zoomOut = () => setImageModal(prev => ({ ...prev, zoom: Math.max(0.5, Number((prev.zoom - 0.25).toFixed(2)) ) }));
  const resetZoom = () => setImageModal(prev => ({ ...prev, zoom: 1 }));

  const loadSelectedPatientHistory = async (patientId) => {
    const requestId = ++historyRequestIdRef.current;
    try {
      if (!patientId) {
        setPatientHistory([]);
        return;
      }

      setPatientHistory([]);
      const res = await api(`/patient-management/patients/${patientId}/history?order=desc`);

      if (requestId !== historyRequestIdRef.current) return;
      if (selectedPatientIdRef.current !== patientId) return;
      setPatientHistory(res.data || []);
    } catch {
      if (requestId !== historyRequestIdRef.current) return;
      if (selectedPatientIdRef.current !== patientId) return;
      setPatientHistory([]);
    }
  };

  useEffect(() => {
    if (chatMode === 'existing' && selectedPatientId) {
      loadSelectedPatientHistory(selectedPatientId);
    } else if (chatMode === 'new' && continueFromHistory && selectedPatientId) {
      loadSelectedPatientHistory(selectedPatientId);
    } else {
      setPatientHistory([]);
    }
  }, [chatMode, continueFromHistory, selectedPatientId]);

  useEffect(() => {
    if (chatMode === 'quick' || !selectedPatientId) return;
    if (chatMode === 'new' && !continueFromHistory) return;

    const seededMessages = historyToChatMessages(patientHistory);
    suppressNextAutoScrollRef.current = true;
    setMessages(seededMessages);
    setAssistantStatus({
      msg: seededMessages.length
        ? 'Loaded previous patient injuries/history into chat.'
        : 'No previous chat history for selected patient.',
      err: false,
    });
  }, [patientHistory, chatMode, continueFromHistory, selectedPatientId]);

  useEffect(() => {
    if (suppressNextAutoScrollRef.current) {
      suppressNextAutoScrollRef.current = false;
      messagesContainerRef.current?.scrollTo({ top: 0, behavior: 'auto' });
      return;
    }
    const container = messagesContainerRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    const preventBrowserFileOpen = (event) => {
      event.preventDefault();
    };

    window.addEventListener('dragover', preventBrowserFileOpen);
    window.addEventListener('drop', preventBrowserFileOpen);
    return () => {
      window.removeEventListener('dragover', preventBrowserFileOpen);
      window.removeEventListener('drop', preventBrowserFileOpen);
    };
  }, []);

  const clearFile = () => {
    if (preview && preview.startsWith('blob:')) URL.revokeObjectURL(preview);
    setSelectedFile(null);
    setPreview('');
    if (fileRef.current) fileRef.current.value = '';
  };

  const createMessageImageUrl = (file) => {
    if (!file || !file.type?.startsWith('image/')) return '';
    const url = URL.createObjectURL(file);
    messageImageUrlsRef.current.add(url);
    return url;
  };

  const setSelectedImageFile = (file) => {
    if (!file || !file.type.startsWith('image/')) return;
    if (preview && preview.startsWith('blob:')) URL.revokeObjectURL(preview);
    setSelectedFile(file);
    setPreview(URL.createObjectURL(file));
  };

  const onSelectFile = (event) => {
    const file = event.target.files?.[0] || null;
    if (!file) return;
    setSelectedImageFile(file);
  };

  const pickDroppedImage = (dataTransfer) => {
    const items = Array.from(dataTransfer?.items || []);
    for (const item of items) {
      if (item.kind !== 'file') continue;
      const file = item.getAsFile();
      if (file && file.type?.startsWith('image/')) return file;
    }

    const files = Array.from(dataTransfer?.files || []);
    return files.find(file => file.type?.startsWith('image/')) || null;
  };

  const hasFileDrag = (event) => {
    const types = event.dataTransfer?.types;
    if (!types) return false;
    return Array.from(types).includes('Files');
  };

  const onDragEnterCard = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!hasFileDrag(event)) return;
    dragDepthRef.current += 1;
    setIsDragging(true);
  };

  const onDropFile = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepthRef.current = 0;
    setIsDragging(false);
    const file = pickDroppedImage(event.dataTransfer);
    if (!file) return;
    setSelectedImageFile(file);
  };

  const onDragOverCard = (event) => {
    event.preventDefault();
    event.stopPropagation();
    if (!hasFileDrag(event)) return;
    if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
    setIsDragging(true);
  };

  const onDragLeaveCard = (event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setIsDragging(false);
    }
  };

  const analyze = async () => {
    const cleanedSymptoms = symptoms.trim();
    const hasSymptoms = Boolean(cleanedSymptoms);
    const hasImage = Boolean(selectedFile);
    if (!hasSymptoms && !hasImage) return;

    const contextSnippet = messages
      .filter(item => item.role === 'user' && item.text)
      .slice(-2)
      .map(item => item.text)
      .join(' | ');

    const historySnippet = (chatMode !== 'quick' && continueFromHistory)
      ? patientHistory
          .slice(0, 3)
          .map(entry => {
            const data = entry?.data || {};
            const type = entry?.entry_type === 'analysis' ? 'analysis' : 'record';
            const label = type === 'analysis' ? (data.disease || 'unknown') : (data.diagnosis || 'unknown');
            return `${type}:${label}`;
          })
          .join(' | ')
      : '';

    const submittedPreview = selectedFile ? createMessageImageUrl(selectedFile) : '';
    const userMessage = { role: 'user', text: cleanedSymptoms, image: submittedPreview };
    suppressNextAutoScrollRef.current = false;
    setMessages(prev => [...prev, userMessage]);
    setSymptoms('');
    setLoading(true);

    try {
      const fd = new FormData();
      const contextualParts = [];
      if (chatMode !== 'quick' && historySnippet) contextualParts.push(`history=${historySnippet}`);
      if (contextSnippet) contextualParts.push(`conversation=${contextSnippet}`);
      if (cleanedSymptoms) contextualParts.push(`current=${cleanedSymptoms}`);
      const mergedSymptoms = contextualParts.join(' | ');
      if (mergedSymptoms) fd.append('symptoms', mergedSymptoms);
      if (selectedFile) fd.append('file', selectedFile);
      const res = await api('/multimodal/analyze', { method: 'POST', body: fd });
      const botMessage = { role: 'bot', data: res, image: submittedPreview };
      const responseMessages = [...messages, userMessage, botMessage];
      setMessages(prev => [...prev, botMessage]);

      if (chatMode === 'existing' && selectedPatientId) {
        await saveChatRecordForPatient(selectedPatientId, {
          suppressStatus: true,
          sourceMessages: responseMessages,
        });
        await saveAnalysisForPatient(res, {
          notifyPopup: false,
          suppressStatus: true,
        });
        setAssistantStatus({ msg: 'Response auto-saved to patient records/history.', err: false });
      }

      if (res?.follow_up_questions?.length) {
        setPrompts(res.follow_up_questions);
      } else {
        setPrompts(buildPrompts(res, hasSymptoms, hasImage));
      }
      clearFile();
    } catch (err) {
      setMessages(prev => [...prev, { role: 'bot', data: { error: err.message } }]);
    } finally {
      setLoading(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); analyze(); }
  };

  const resolveDoctorId = async () => {
    let user = null;
    try { user = JSON.parse(localStorage.getItem('pulseUser') || 'null'); } catch { user = null; }
    let doctorId = user?.doctor_id;
    if (!doctorId) {
      const validated = await api('/auth/validate');
      const freshUser = validated?.user || null;
      if (freshUser) {
        localStorage.setItem('pulseUser', JSON.stringify(freshUser));
        doctorId = freshUser.doctor_id;
      }
    }
    if (!doctorId) throw new Error('Doctor profile is missing. Please login as an approved doctor.');
    return doctorId;
  };

  const saveChatRecordForPatient = async (patientId, options = {}) => {
    const { suppressStatus = false, sourceMessages = null } = options;
    if (!patientId) throw new Error('Patient is required to save chat record');

    const transcriptSource = Array.isArray(sourceMessages) ? sourceMessages : messages;
    if (!transcriptSource.length) return;

    const doctorId = await resolveDoctorId();
    const latestBot = [...transcriptSource].reverse().find(item => item.role === 'bot' && item.data && !item.data.error);
    const diagnosis = latestBot?.data?.condition || 'chat_consultation';
    const latestUser = [...transcriptSource].reverse().find(item => item.role === 'user');
    const isGeneralChatSave = latestBot?.data?.response_type === 'chat';

    const notesSource = isGeneralChatSave
      ? [latestUser, latestBot].filter(Boolean)
      : transcriptSource;

    const transcript = notesSource
      .map((item) => {
        if (!item) return '';
        if (item.role === 'user') {
          return item.text || (item.image ? '[image uploaded]' : '[no text]');
        }
        if (item.data?.error) {
          return `Error: ${item.data.error}`;
        }
        if (item.data?.response_type === 'chat' && item.data?.chat_response) {
          return item.data.chat_response;
        }
        const doctorNote = String(item.data?.recommendation?.doctor_note || '').trim();
        if (doctorNote) {
          return doctorNote;
        }
        const plainNotes = String(item.data?.notes || '').trim();
        if (plainNotes) {
          return plainNotes;
        }
        const condition = item.data?.condition || 'n/a';
        const confidence = Number(item.data?.confidence || 0).toFixed(3);
        const risk = item.data?.risk_level || 'n/a';
        return `${condition} (${confidence}, ${risk})`;
      })
      .filter(Boolean)
      .join('\n')
      .slice(0, 6000);

    await api('/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        doctor_id: doctorId,
        patient_id: patientId,
        diagnosis,
        notes: transcript,
        status: 'approved',
      }),
    });

    if (!suppressStatus) {
      setAssistantStatus({ msg: 'Chat transcript saved to patient records.', err: false });
    }
  };

  const createPatientFromAssistant = async () => {
    if (isCreatingPatient) return;
    setIsCreatingPatient(true);
    try {
      if (!newPatient.full_name.trim()) throw new Error('Patient name is required');
      const payload = {
        full_name: newPatient.full_name.trim(),
        date_of_birth: newPatient.date_of_birth || null,
        email: newPatient.email || null,
        phone: newPatient.phone || null,
      };
      const res = await api('/patient-management/patients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const created = res?.data;
      const refreshed = await api('/patient-management/patients');
      setPatients(refreshed.data || []);
      const createdPatientId = created?.id;
      if (createdPatientId) {
        setSelectedPatientId(createdPatientId);

        if (messages.length > 0) {
          await saveChatRecordForPatient(createdPatientId, { suppressStatus: true });
        }

        const analysisMessages = messages.filter(
          (item) => item.role === 'bot' && item.data && !item.data.error,
        );

        if (analysisMessages.length > 0) {
          for (const item of analysisMessages) {
            await saveAnalysisForPatient(item.data, {
              notifyPopup: false,
              patientId: createdPatientId,
              suppressStatus: true,
            });
          }
          setAssistantStatus({ msg: 'Patient created and chat saved to records/history.', err: false });
        } else {
          setAssistantStatus({ msg: 'Patient created and switched to history mode.', err: false });
        }

        setChatMode('existing');
        setContinueFromHistory(true);
        await loadSelectedPatientHistory(createdPatientId);
      }
      setNewPatient({ full_name: '', date_of_birth: '', email: '', phone: '' });
      showPopup('Patient added');
    } catch (err) {
      const message = String(err.message || 'Unable to add patient');
      if (message.toLowerCase().includes('already exists')) {
        const refreshed = await api('/patient-management/patients').catch(() => ({ data: [] }));
        setPatients(refreshed.data || []);
        const match = message.match(/ID:\s*([a-zA-Z0-9-]+)/);
        if (match?.[1]) {
          setSelectedPatientId(match[1]);
          setChatMode('existing');
          setContinueFromHistory(true);
          await loadSelectedPatientHistory(match[1]);
        }
        showPopup('Patient added');
        setAssistantStatus({ msg: 'Patient already exists and is available for selection.', err: false });
      } else {
        setAssistantStatus({ msg: message, err: true });
        showPopup(message, true);
      }
    } finally {
      setIsCreatingPatient(false);
    }
  };

  const saveLatestAnalysis = async () => {
    try {
      if (chatMode === 'quick') throw new Error('Saving is disabled in General chat (no save) mode');
      if (!selectedPatientId) throw new Error('Select a patient first');

      const latest = [...messages].reverse().find(item => item.role === 'bot' && item.data && !item.data.error)?.data;
      if (!latest) throw new Error('Run analysis first');

      await saveAnalysisForPatient(latest, { notifyPopup: true, successStatus: 'Latest analysis saved to selected patient' });
    } catch (err) {
      setAssistantStatus({ msg: err.message, err: true });
      showPopup(String(err.message || 'Save failed'), true);
    }
  };

  const saveAnalysisForPatient = async (analysisData, options = {}) => {
    const {
      notifyPopup = false,
      successStatus = 'Latest analysis saved to selected patient',
      patientId = null,
      suppressStatus = false,
    } = options;

    const targetPatientId = patientId || selectedPatientId;
    if (!targetPatientId) throw new Error('Select a patient first');
    if (!analysisData) throw new Error('Run analysis first');

    const doctorId = await resolveDoctorId();

    const confidence = Number(analysisData.confidence || 0);
    let severity = 'moderate';
    if (confidence >= 0.85) severity = 'critical';
    else if (confidence >= 0.65) severity = 'high';
    else if (confidence < 0.4) severity = 'low';

    const risk = ['low', 'medium', 'high'].includes(String(analysisData.risk_level || '').toLowerCase())
      ? String(analysisData.risk_level).toLowerCase()
      : 'medium';

    const payload = {
      patient_id: targetPatientId,
      doctor_id: doctorId,
      disease: analysisData.condition || 'general_non_specific_finding',
      probability: Math.max(0, Math.min(1, confidence)),
      severity,
      risk,
      uncertainty: Math.max(0, Math.min(1, 1 - confidence)),
      recommendations: analysisData.recommendation || {},
      follow_up_questions: analysisData.follow_up_questions || [],
      sources: { frontend: 'assistant_tab' },
      notes: null,
    };

    await api('/patient-management/analysis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!suppressStatus) {
      setAssistantStatus({ msg: successStatus, err: false });
    }
    if (notifyPopup) showPopup('Chat saved to patient');
  };

  const deleteMessageAt = (index) => {
    setMessages((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
    setAssistantStatus({ msg: 'Chat message deleted.', err: false });
  };

  return (
    <div
      className="space-y-6 animate-fade-up"
      onDragEnter={onDragEnterCard}
      onDragOver={onDragOverCard}
      onDragLeave={onDragLeaveCard}
      onDrop={onDropFile}
    >
      <SectionTitle icon={MessageCircle}>Unified Assistant</SectionTitle>

      {popup.open && (
        <div className={`fixed top-5 right-5 z-60 px-4 py-2 rounded-xl border text-sm shadow-lg ${popup.error ? 'bg-red-600/20 border-red-400/40 text-red-200' : 'bg-emerald-600/20 border-emerald-400/40 text-emerald-200'}`}>
          {popup.text}
        </div>
      )}

      {imageModal.open && (
        <div
          className="fixed inset-0 z-60 bg-black/80 backdrop-blur-sm flex flex-col"
          onClick={closeImageModal}
        >
          <div className="px-4 py-3 border-b border-white/10 bg-black/50 flex items-center justify-between gap-3">
            <p className="text-sm text-slate-200 truncate">{imageModal.alt}</p>
            <div className="flex items-center gap-2">
              <button onClick={(event) => { event.stopPropagation(); zoomOut(); }} className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm">-</button>
              <button onClick={(event) => { event.stopPropagation(); resetZoom(); }} className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-xs">100%</button>
              <button onClick={(event) => { event.stopPropagation(); zoomIn(); }} className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white text-sm">+</button>
              <button onClick={(event) => { event.stopPropagation(); closeImageModal(); }} className="px-3 py-1.5 rounded-lg bg-red-600/20 hover:bg-red-600/35 text-red-200 text-xs">Close</button>
            </div>
          </div>
          <div
            className="flex-1 overflow-auto p-4 flex items-center justify-center"
            onClick={(event) => event.stopPropagation()}
            onWheel={(event) => {
              event.preventDefault();
              if (event.deltaY < 0) setZoom(imageModal.zoom + 0.1);
              else setZoom(imageModal.zoom - 0.1);
            }}
          >
            <div style={{ transform: `scale(${imageModal.zoom})`, transformOrigin: 'center center' }}>
              {imageModal.analysisData ? (
                <DetectionOverlayImage
                  image={imageModal.src}
                  data={imageModal.analysisData}
                  mode="modal"
                />
              ) : (
                <img
                  src={imageModal.src}
                  alt={imageModal.alt}
                  className="max-w-none rounded-lg border border-white/15 shadow-lg"
                />
              )}
            </div>
          </div>
        </div>
      )}

      <GlassCard>
        <h3 className="text-sm font-semibold text-white mb-3">Assistant Mode</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          <button
            onClick={() => setChatMode('quick')}
            className={`rounded-xl px-3 py-2.5 text-left text-sm border backdrop-blur-sm transition ${chatMode === 'quick' ? 'bg-purple-500/15 border-purple-400/40 text-purple-100 shadow-[0_0_15px_rgba(168,85,247,0.15)]' : 'bg-white/[0.04] border-white/10 text-slate-300 hover:bg-white/[0.08]'}`}
          >
            <p className="font-semibold">General chat (no save)</p>
            <p className="text-xs text-slate-400 mt-1">No patient linkage and no history save.</p>
          </button>
          <button
            onClick={() => setChatMode('existing')}
            className={`rounded-xl px-3 py-2.5 text-left text-sm border backdrop-blur-sm transition ${chatMode === 'existing' ? 'bg-purple-500/15 border-purple-400/40 text-purple-100 shadow-[0_0_15px_rgba(168,85,247,0.15)]' : 'bg-white/[0.04] border-white/10 text-slate-300 hover:bg-white/[0.08]'}`}
          >
            <p className="font-semibold">History mode</p>
            <p className="text-xs text-slate-400 mt-1">Continue with prior history and save under existing patient.</p>
          </button>
          <button
            onClick={() => {
              setChatMode('new');
              showPopup('Scroll down to the bottom to add the patient.');
            }}
            className={`rounded-xl px-3 py-2.5 text-left text-sm border backdrop-blur-sm transition ${chatMode === 'new' ? 'bg-purple-500/15 border-purple-400/40 text-purple-100 shadow-[0_0_15px_rgba(168,85,247,0.15)]' : 'bg-white/[0.04] border-white/10 text-slate-300 hover:bg-white/[0.08]'}`}
          >
            <p className="font-semibold">Add new patient</p>
            <p className="text-xs text-slate-400 mt-1">Create patient below, then save chat to that patient.</p>
          </button>
        </div>
      </GlassCard>

      <GlassCard
        className={`relative flex flex-col h-130 transition ${isDragging ? 'border border-fuchsia-400/50 bg-fuchsia-500/[0.06] shadow-[0_0_30px_rgba(217,70,239,0.12)]' : ''}`}
        onDragEnter={onDragEnterCard}
        onDragOver={onDragOverCard}
        onDragLeave={onDragLeaveCard}
        onDrop={onDropFile}
      >
        {isDragging && (
          <div className="pointer-events-none absolute inset-0 z-20 rounded-2xl border-2 border-dashed border-fuchsia-400/60 bg-fuchsia-500/10 backdrop-blur-sm flex items-center justify-center">
            <p className="text-sm text-white font-semibold drop-shadow-[0_0_8px_rgba(217,70,239,0.6)]">Drop image to attach</p>
          </div>
        )}
        {/* Messages area */}
        <div ref={messagesContainerRef} className="flex-1 overflow-y-auto space-y-4 mb-4 pr-1">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-slate-500">
              <Bot size={40} className="mb-3 text-purple-400/60" />
              <p className="text-sm">Send symptoms, attach an image, or provide both in one request</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.role === 'bot' && (
                <div className="w-8 h-8 rounded-xl bg-purple-500/15 border border-purple-400/20 flex items-center justify-center shrink-0 mt-1">
                  <Bot size={16} className="text-purple-300" />
                </div>
              )}
              <div className={`max-w-[75%] rounded-2xl px-4 py-3 pr-16 text-sm ${
                m.role === 'user'
                  ? 'bg-fuchsia-500/20 text-white rounded-br-md border border-fuchsia-300/20 shadow-[0_2px_15px_rgba(217,70,239,0.1)]'
                  : 'bg-white/[0.06] text-slate-200 rounded-bl-md border border-white/[0.1] backdrop-blur-sm'
              } relative`}>
                <button
                  onClick={() => deleteMessageAt(i)}
                  className="absolute top-2 right-2 text-[10px] px-2 py-0.5 rounded bg-black/30 hover:bg-red-500/30 text-slate-300 hover:text-red-200 transition"
                >
                  Delete
                </button>
                {m.role === 'user' ? (
                  <div className="space-y-2">
                    {m.text ? <p className="whitespace-pre-wrap">{m.text}</p> : <p className="text-slate-300 italic">Image only</p>}
                    {m.image && (
                      <img
                        src={m.image}
                        alt="Attached"
                        className="max-h-40 rounded-lg border border-white/10 cursor-zoom-in"
                        onClick={() => openImageModal(m.image, 'Attached image')}
                      />
                    )}
                  </div>
                ) : m.data?.error ? (
                  <p className="text-red-400">{m.data.error}</p>
                ) : m.data?.response_type === 'chat' && m.data?.chat_response ? (
                  <div className="space-y-2">
                    <p className="whitespace-pre-wrap text-slate-200 leading-relaxed">{m.data.chat_response}</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <p><span className="text-slate-400">Condition:</span> <span className="font-semibold text-white">{m.data.condition || '—'}</span></p>
                    <p><span className="text-slate-400">Confidence:</span> {Number(m.data.confidence || 0).toFixed(3)}</p>
                    <p><span className="text-slate-400">Risk:</span> <Badge level={m.data.risk_level || 'low'} /></p>
                    <DetectionOverlayImage image={m.image} data={m.data} onOpenImage={openImageModal} />
                    {m.data.recommendation && typeof m.data.recommendation === 'object' && Object.keys(m.data.recommendation).length > 0 && (
                      <div className="text-xs bg-black/20 rounded-lg p-2 space-y-2">
                        <p className="text-slate-300 font-semibold">Suggested next steps</p>
                        <p><span className="text-slate-400">Most apt drug:</span> {m.data.recommendation.primary_drug || ((m.data.recommendation.drugs || [])[0] || 'No specific medication suggested without clinician confirmation.')}</p>
                        <p><span className="text-slate-400">Procedures:</span> {(m.data.recommendation.procedures || []).length ? (m.data.recommendation.procedures || []).join(', ') : 'Clinical reassessment advised.'}</p>
                        <p><span className="text-slate-400">Tests:</span> {(m.data.recommendation.tests || []).length ? (m.data.recommendation.tests || []).join(', ') : 'Further targeted tests may be needed.'}</p>
                        {(m.data.recommendation.guideline_sources || []).length > 0 && (
                          <p><span className="text-slate-400">Guideline sources:</span> {(m.data.recommendation.guideline_sources || []).join('; ')}</p>
                        )}
                        {m.data.recommendation.doctor_note && (
                          <p>{m.data.recommendation.doctor_note}</p>
                        )}
                      </div>
                    )}
                    {m.data.follow_up_questions?.length > 0 && (
                      <div>
                        <span className="text-slate-400">Follow-up:</span>
                        <ul className="list-disc pl-4 mt-1 space-y-1 text-xs text-slate-300">
                          {m.data.follow_up_questions.map((q, idx) => (<li key={idx}>{q}</li>))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
              {m.role === 'user' && (
                <div className="w-8 h-8 rounded-xl bg-fuchsia-500/15 border border-fuchsia-400/20 flex items-center justify-center shrink-0 mt-1">
                  <User size={16} className="text-fuchsia-300" />
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-xl bg-purple-500/15 border border-purple-400/20 flex items-center justify-center">
                <Bot size={16} className="text-purple-300 animate-pulse" />
              </div>
              <div className="bg-white/[0.06] border border-white/[0.1] backdrop-blur-sm rounded-2xl rounded-bl-md px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input bar */}
        <div className={`rounded-xl p-2 transition ${isDragging ? 'bg-fuchsia-500/[0.06] border border-fuchsia-400/30' : ''}`}>
          <div className="flex gap-2 items-end">
          <textarea
            value={symptoms}
            onChange={e => setSymptoms(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Type symptoms (optional if you attach an image)…"
            rows={2}
            className="glass-input flex-1 rounded-xl px-4 py-3 text-sm text-white placeholder:text-slate-500 resize-none"
          />
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onSelectFile} />
          <button
            onClick={() => fileRef.current?.click()}
            className="w-11 h-11 rounded-xl bg-white/10 hover:bg-white/20 text-white flex items-center justify-center transition cursor-pointer shrink-0"
            title="Attach image"
          >
            <Paperclip size={17} />
          </button>
          <button
            onClick={analyze}
            disabled={loading || (!symptoms.trim() && !selectedFile)}
            className="w-11 h-11 rounded-xl bg-gradient-to-br from-purple-600 to-fuchsia-600 hover:from-purple-500 hover:to-fuchsia-500 text-white flex items-center justify-center transition disabled:opacity-40 cursor-pointer shrink-0 shadow-[0_0_15px_rgba(168,85,247,0.3)]"
          >
            <Send size={18} />
          </button>
          </div>
          <p className="mt-1.5 px-2.5 py-1 text-[11px] text-slate-300 font-medium bg-white/[0.06] border border-white/[0.1] rounded-lg inline-block backdrop-blur-sm">Drag and drop an image here, or use the attach button</p>
        </div>
        {selectedFile && (
          <div className="mt-3 p-2 rounded-xl bg-white/5 border border-white/10 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              {preview ? (
                <img
                  src={preview}
                  alt="Preview"
                  className="w-12 h-12 rounded-lg object-cover border border-white/10 cursor-zoom-in"
                  onClick={() => openImageModal(preview, 'Selected image preview')}
                />
              ) : null}
              <p className="text-xs text-slate-300 truncate">{selectedFile.name}</p>
            </div>
            <button onClick={clearFile} className="w-8 h-8 rounded-lg bg-white/10 hover:bg-red-500/20 text-slate-300 hover:text-red-300 flex items-center justify-center transition">
              <X size={14} />
            </button>
          </div>
        )}
      </GlassCard>

      {chatMode !== 'quick' && (
        <GlassCard>
          <h3 className="text-sm font-semibold text-white mb-3">
            {chatMode === 'new' ? 'Add New Patient' : 'History Mode'}
          </h3>

          {chatMode === 'existing' && (
            <div className="space-y-3 max-w-xl">
              <label className="flex flex-col gap-1.5 text-sm text-slate-300">
                Selected Patient
                <select
                  value={selectedPatientId}
                  onChange={e => {
                    const nextPatientId = e.target.value;
                    setContinueFromHistory(true);
                    setSelectedPatientId(nextPatientId);
                    suppressNextAutoScrollRef.current = true;
                    setMessages([]);
                    setAssistantStatus({ msg: 'Loading selected patient history...', err: false });
                  }}
                  className="glass-input rounded-xl px-3.5 py-2.5 text-sm text-white"
                >
                  <option value="">Select patient</option>
                  {patients.map(patient => (
                    <option key={patient.id} value={patient.id}>{patient.full_name}</option>
                  ))}
                </select>
              </label>

              <Btn onClick={saveLatestAnalysis}>Save Latest Analysis</Btn>
            </div>
          )}

          {chatMode === 'new' && (
            <div className="space-y-3 max-w-2xl">
              <Input
                label="New Patient Name"
                value={newPatient.full_name}
                onChange={e => setNewPatient(prev => ({ ...prev, full_name: e.target.value }))}
                placeholder="Enter full name"
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="DOB"
                  type="date"
                  value={newPatient.date_of_birth}
                  onChange={e => setNewPatient(prev => ({ ...prev, date_of_birth: e.target.value }))}
                />
                <Input
                  label="Phone"
                  value={newPatient.phone}
                  onChange={e => setNewPatient(prev => ({ ...prev, phone: e.target.value }))}
                  placeholder="+1..."
                />
              </div>
              <Input
                label="Email"
                type="email"
                value={newPatient.email}
                onChange={e => setNewPatient(prev => ({ ...prev, email: e.target.value }))}
                placeholder="patient@email.com"
              />
              <div className="flex flex-wrap items-center gap-2">
                <Btn variant="secondary" onClick={createPatientFromAssistant} disabled={isCreatingPatient}>
                  {isCreatingPatient ? 'Adding Patient…' : 'Add Patient'}
                </Btn>
              </div>
            </div>
          )}

          <StatusMsg msg={assistantStatus.msg} isError={assistantStatus.err} />
        </GlassCard>
      )}

      {/* Dynamic prompts */}
      <GlassCard>
        <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Sparkles size={15} className="text-fuchsia-400" /> Suggested Prompts
        </h3>
        <div className="flex flex-wrap gap-2">
          {prompts.map((p, i) => (
            <button key={i} onClick={() => setSymptoms(prev => prev ? `${prev}\n- ${p}` : p)}
              className="px-3 py-1.5 rounded-full text-xs bg-purple-500/10 text-purple-200 border border-purple-400/20 hover:bg-purple-500/20 hover:border-purple-400/35 transition cursor-pointer backdrop-blur-sm">
              {p}
            </button>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}
