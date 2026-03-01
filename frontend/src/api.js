// ─── API helper ───
const CLOUD_BASE = 'https://pulse-ai-b601.onrender.com/api/v1';
const LOCAL_BASE = 'http://127.0.0.1:8000/api/v1';

function isLocal() {
  try { return ['localhost', '127.0.0.1'].includes(window.location.hostname); }
  catch { return false; }
}

export function getBaseUrl() {
  return isLocal() ? LOCAL_BASE : CLOUD_BASE;
}

export function setBaseUrl() {
  // no-op, kept for backward compat
}

function parseApiError(data, statusText) {
  const raw = data?.detail ?? data?.error ?? statusText;

  if (Array.isArray(raw)) {
    const first = raw[0];
    if (typeof first === 'string') return first;
    if (first && typeof first === 'object') {
      const loc = Array.isArray(first.loc) ? first.loc.join(' > ') : first.loc;
      const msg = first.msg || first.message;
      if (loc && msg) return `${loc}: ${msg}`;
      if (msg) return String(msg);
    }
    return 'Request validation failed';
  }

  if (raw && typeof raw === 'object') {
    if (typeof raw.message === 'string') return raw.message;
    if (typeof raw.msg === 'string') return raw.msg;
    return 'Request failed';
  }

  return String(raw || 'Request failed');
}

export async function api(path, options = {}, auth = true) {
  const headers = { ...(options.headers || {}) };
  const token = localStorage.getItem('pulseToken');
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${getBaseUrl()}${path}`, { ...options, headers });

  let data = {};
  try { data = await res.json(); } catch { data = {}; }

  if (!res.ok) {
    throw new Error(parseApiError(data, res.statusText));
  }
  return data;
}
