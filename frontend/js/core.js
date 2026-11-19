/* Shared helpers, state and the API client. */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const inr = n => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR'}).format(n);
const S = { access: localStorage.getItem('at'), refresh: localStorage.getItem('rt'), user: null, tab: 'overview', page: 1, editing: null, chat: [] };

/* ---------- API ---------- */
function setTokens(t) {
  S.access = t?.access_token || null; S.refresh = t?.refresh_token || null;
  t ? (localStorage.setItem('at', S.access), localStorage.setItem('rt', S.refresh)) : (localStorage.removeItem('at'), localStorage.removeItem('rt'));
}
async function refreshTokens() {
  if (!S.refresh) return false;
  const r = await fetch(API_BASE + '/api/auth/refresh', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({refresh_token: S.refresh})});
  if (!r.ok) return false;
  setTokens(await r.json()); return true;
}
async function api(path, {method='GET', json, form, raw} = {}, retry = true) {
  const headers = {};
  if (S.access) headers.Authorization = 'Bearer ' + S.access;
  if (json) headers['Content-Type'] = 'application/json';
  const r = await fetch(API_BASE + path, {method, headers, body: json ? JSON.stringify(json) : form});
  if (r.status === 401 && retry && S.refresh && await refreshTokens()) return api(path, {method, json, form, raw}, false);
  if (r.status === 401 && !path.startsWith('/api/auth/')) { logout(); throw new Error('Please sign in again'); }
  if (!r.ok) {
    let msg = r.statusText;
    try { const b = await r.json(); msg = typeof b.detail === 'string' ? b.detail : (b.detail?.[0]?.msg || msg); } catch {}
    throw new Error(msg);
  }
  if (raw) return r;
  return r.status === 204 ? null : r.json();
}
