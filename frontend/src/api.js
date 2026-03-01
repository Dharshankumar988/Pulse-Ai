// ─── API helper ───
const LOCAL_DEFAULT_BASE = 'http://127.0.0.1:8000/api/v1';
const CLOUD_DEFAULT_BASE = 'https://pulse-ai-b601.onrender.com/api/v1';

function normalizeBase(url) {
  return String(url || '').trim().replace(/\/+$/, '');
}

function ensureApiPrefix(url) {
  const normalized = normalizeBase(url);
  if (!normalized) return '';
  return normalized.endsWith('/api/v1') ? normalized : `${normalized}/api/v1`;
}

function isLocalHost(hostname) {
  return hostname === 'localhost' || hostname === '127.0.0.1';
}

const ENV_BASE = ensureApiPrefix(import.meta.env.VITE_API_BASE_URL || '');

export function getBaseUrl() {
  const stored = ensureApiPrefix(localStorage.getItem('pulseApiBase'));
  const isBrowser = typeof window !== 'undefined';
  const isLocalRuntime = isBrowser ? isLocalHost(window.location.hostname) : false;

  if (stored) {
    const isInsecureHttp = stored.startsWith('http://');
    if (!(isInsecureHttp && !isLocalRuntime)) {
      return stored;
    }
  }

  if (ENV_BASE) return ENV_BASE;
  return isLocalRuntime ? LOCAL_DEFAULT_BASE : CLOUD_DEFAULT_BASE;
}

export function setBaseUrl(url) {
  localStorage.setItem('pulseApiBase', ensureApiPrefix(url));
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
