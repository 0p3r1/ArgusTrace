// The backend is loopback-only by default. Both values can be overridden at
// build time (VITE_ARGUSTRACE_API_BASE / VITE_ARGUSTRACE_TOKEN) for the case
// where the API is served somewhere else behind a shared token.
export const API_BASE = import.meta.env.VITE_ARGUSTRACE_API_BASE || 'http://127.0.0.1:8000'

const TOKEN = import.meta.env.VITE_ARGUSTRACE_TOKEN || ''

// Only sent when configured: the API requires no token by default, and an
// empty header would just be noise on every request.
export function authHeaders() {
  return TOKEN ? { 'X-ArgusTrace-Token': TOKEN } : {}
}

// Same shape as fetch, with the token attached. Report downloads are plain
// <a href> links and can't carry a header, so they stay unauthenticated —
// which is fine while the token is unset, and is why the token is an opt-in
// for remote setups rather than the default.
export function apiFetch(url, options = {}) {
  return fetch(url, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  })
}
