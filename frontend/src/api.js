// ─── API helper ───
const DEFAULT_BASE = 'http://127.0.0.1:8000/api/v1';

export function getBaseUrl() {
  return localStorage.getItem('pulseApiBase') || DEFAULT_BASE;
}

export function setBaseUrl(url) {
  localStorage.setItem('pulseApiBase', url);
}

export async function api(path, options = {}, auth = true) {
  const headers = { ...(options.headers || {}) };
  const token = localStorage.getItem('pulseToken');
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${getBaseUrl()}${path}`, { ...options, headers });

  let data = {};
  try { data = await res.json(); } catch { data = {}; }

  if (!res.ok) {
    throw new Error(data.detail || data.error || res.statusText);
  }
  return data;
}
