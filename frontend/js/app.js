/* Screens and event wiring. Depends on core.js. */
/* ---------- auth ---------- */
let registering = false;
function showAuth() {
  $('#app').classList.add('hidden'); $('#auth').classList.remove('hidden');
  $('#auth-sub').textContent = registering ? 'Create an account to start your ledger.' : 'Sign in to see your spending.';
  $('#a-go').textContent = registering ? 'Create account' : 'Sign in';
  $('#a-switch-text').textContent = registering ? 'Already have an account?' : 'No account yet?';
  $('#a-switch').textContent = registering ? 'Sign in' : 'Create one';
  $('#a-pass').autocomplete = registering ? 'new-password' : 'current-password';
}
$('#a-switch').onclick = () => { registering = !registering; $('#a-err').textContent = ''; showAuth(); };
async function submitAuth() {
  $('#a-err').textContent = '';
  try {
    const t = await api(registering ? '/api/auth/register' : '/api/auth/login', {method:'POST', json:{email:$('#a-email').value.trim(), password:$('#a-pass').value}}, false);
    setTokens(t); $('#a-pass').value = ''; await boot();
  } catch (e) { $('#a-err').textContent = e.message; }
}
$('#a-go').onclick = submitAuth;
$('#a-pass').addEventListener('keydown', e => { if (e.key === 'Enter') submitAuth(); });
function logout() { setTokens(null); S.user = null; S.chat = []; showAuth(); }
$('#logout').onclick = logout;

async function boot() {
  if (!S.access) return showAuth();
  try { S.user = await api('/api/auth/me'); } catch { return; }
  $('#auth').classList.add('hidden'); $('#app').classList.remove('hidden');
  $('#who').textContent = S.user.email + (S.user.role === 'admin' ? ' (admin)' : '');
  go(S.tab);
}

/* ---------- navigation ---------- */
function go(tab) {
  S.tab = tab;
  document.querySelectorAll('#nav button').forEach(b => b.setAttribute('aria-current', b.dataset.tab === tab ? 'page' : 'false'));
  ({overview: viewOverview, expenses: viewExpenses, chat: viewChat})[tab]();
}
$('#nav').onclick = e => e.target.dataset.tab && go(e.target.dataset.tab);

/* ---------- overview ---------- */
const pad = n => String(n).padStart(2, '0');
const todayStr = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const daysIn = k => { const [y, m] = k.split('-').map(Number); return new Date(y, m, 0).getDate(); };
const shiftMonth = (k, n) => { const [y, m] = k.split('-').map(Number); const d = new Date(y, m - 1 + n, 1); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`; };
const mname = (k, long) => new Date(k + '-01T00:00:00').toLocaleString('en-IN', {month: long ? 'long' : 'short', year: long ? 'numeric' : '2-digit'});
const compact = n => new Intl.NumberFormat('en-IN', {notation: 'compact', maximumFractionDigits: 1}).format(n);
const niceMax = v => { if (v <= 0) return 1; const p = 10 ** Math.floor(Math.log10(v)), f = v / p; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p; };
let ovMonth = todayStr().slice(0, 7);

function barChart(items, {highlight = -1, every = 1, avg = 0, label = 'Bar chart', all = false} = {}) {
  const W = 640, H = 210, L = 48, R = 8, T = 10, B = 26, iw = W - L - R, ih = H - T - B;
  const max = niceMax(Math.max(...items.map(i => i.value), 0)), bw = iw / items.length;
  const grid = [0, 1, 2, 3, 4].map(k => {
    const y = T + ih - ih * k / 4;
    return `<line class="gl" x1="${L}" x2="${W - R}" y1="${y}" y2="${y}"/><text class="ax" x="${L - 6}" y="${y + 4}" text-anchor="end">${compact(max * k / 4)}</text>`;
  }).join('');
  const bars = items.map((it, i) => {
    const h = it.value / max * ih, x = L + i * bw + bw * 0.18, w = bw * 0.64;
    return `<rect class="bar${all || i === highlight ? ' hi' : ''}" x="${x}" y="${T + ih - h}" width="${w}" height="${it.value > 0 ? Math.max(h, 1) : 0}" rx="2"><title>${esc(it.tip)}</title></rect>`
      + (i % every === 0 ? `<text class="ax" x="${x + w / 2}" y="${H - 8}" text-anchor="middle">${esc(it.label)}</text>` : '');
  }).join('');
  const ay = T + ih - avg / max * ih;
  const avgLine = avg > 0 && avg <= max ? `<line class="avg" x1="${L}" x2="${W - R}" y1="${ay}" y2="${ay}"><title>Daily average ${inr(avg)}</title></line>` : '';
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">${grid}${bars}${avgLine}</svg>`;
}

function donut(groups, total) {
  let rows = groups.slice(0, 5);
  if (groups.length > 5) rows.push({key: 'Other', total: groups.slice(5).reduce((s, g) => s + g.total, 0), count: 0});
  let acc = 0;
  const segs = rows.map((g, i) => {
    const pct = g.total / total * 100;
    const c = `<circle cx="21" cy="21" r="15.9155" fill="none" style="stroke:var(--c${i + 1})" stroke-width="5" stroke-dasharray="${pct} ${100 - pct}" stroke-dashoffset="${25 - acc}"><title>${esc(g.key)}: ${inr(g.total)}</title></circle>`;
    acc += pct; return c;
  }).join('');
  const legend = rows.map((g, i) => `<div class="lg"><span class="dot" style="background:var(--c${i + 1})"></span><span class="lbl">${esc(g.key)}</span><span class="num">${inr(g.total)}</span><span class="pct num">${Math.round(g.total / total * 100)}%</span></div>`).join('');
  return `<div class="donut-wrap"><svg class="donut" viewBox="0 0 42 42" role="img" aria-label="Spending by category">
    <circle cx="21" cy="21" r="15.9155" fill="none" style="stroke:var(--paper)" stroke-width="5"/>${segs}
    <text x="21" y="20.5" text-anchor="middle" class="dt">${esc(compact(total))}</text><text x="21" y="26" text-anchor="middle" class="ds">total</text></svg>
    <div class="legend">${legend}</div></div>`;
}

async function viewOverview() {
  $('#view').innerHTML = `
    <div class="toolbar"><div><h2 style="margin:0">Overview</h2><div class="sub">${esc(mname(ovMonth, true))}</div></div>
      <div class="monthnav"><button id="m-prev" aria-label="Previous month">‹</button><input id="ov-m" type="month" value="${ovMonth}" aria-label="Month"><button id="m-next" aria-label="Next month">›</button><button class="primary" id="ov-add">Add expense</button></div></div>
    <div id="ov"><div class="empty">Loading…</div></div>`;
  const setMonth = k => { if (k) { ovMonth = k; viewOverview(); } };
  $('#m-prev').onclick = () => setMonth(shiftMonth(ovMonth, -1));
  $('#m-next').onclick = () => setMonth(shiftMonth(ovMonth, 1));
  $('#ov-m').onchange = e => setMonth(e.target.value);
  $('#ov-add').onclick = () => openForm();

  const n = daysIn(ovMonth), from = `${ovMonth}-01`, to = `${ovMonth}-${pad(n)}`, start = shiftMonth(ovMonth, -5);
  try {
    const [cat, day, trend, recent] = await Promise.all([
      api(`/api/expenses/summary?group_by=category&date_from=${from}&date_to=${to}`),
      api(`/api/expenses/summary?group_by=day&date_from=${from}&date_to=${to}`),
      api(`/api/expenses/summary?group_by=month&date_from=${start}-01&date_to=${to}`),
      api(`/api/expenses?date_from=${from}&date_to=${to}&page_size=5`),
    ]);
    if (trend.count === 0) {
      $('#ov').innerHTML = `<div class="panel onboard"><h3 class="serif">Start your ledger</h3><p>Add your first expense and this page fills up with totals, a daily chart and a category breakdown.</p><button class="primary" id="ob-add">Add your first expense</button></div>`;
      $('#ob-add').onclick = () => openForm(); return;
    }
    const months = [-5, -4, -3, -2, -1, 0].map(i => shiftMonth(ovMonth, i));
    const tmap = Object.fromEntries(trend.groups.map(g => [g.key, g.total]));
    const mItems = months.map(k => ({label: mname(k), value: tmap[k] || 0, tip: `${mname(k, true)}: ${inr(tmap[k] || 0)}`}));
    const dmap = Object.fromEntries(day.groups.map(g => [g.key.slice(8, 10), g.total]));
    const dItems = Array.from({length: n}, (_, i) => { const k = pad(i + 1); return {label: String(i + 1), value: dmap[k] || 0, tip: `${i + 1} ${mname(ovMonth)}: ${inr(dmap[k] || 0)}`}; });
    const elapsed = ovMonth === todayStr().slice(0, 7) ? Number(todayStr().slice(8)) : n;
    const avg = cat.total / elapsed, prev = mItems[4].value;
    const delta = prev > 0 ? (cat.total - prev) / prev * 100 : null;
    const top = cat.groups[0];
    const deltaHtml = delta === null ? `<span class="sub">no data for ${esc(mname(shiftMonth(ovMonth, -1)))}</span>`
      : `<span class="${delta > 0 ? 'up' : 'down'}">${delta > 0 ? '▲' : '▼'} ${Math.abs(delta).toFixed(0)}%</span> <span class="sub">vs ${esc(mname(shiftMonth(ovMonth, -1)))}</span>`;

    $('#ov').innerHTML = `
      <div class="kpis">
        <div class="kpi"><div class="k">Spent</div><div class="v num">${inr(cat.total)}</div><div class="s">${deltaHtml}</div></div>
        <div class="kpi"><div class="k">Daily average</div><div class="v num">${inr(avg)}</div><div class="s sub">over ${elapsed} ${elapsed === 1 ? 'day' : 'days'}</div></div>
        <div class="kpi"><div class="k">Expenses</div><div class="v num">${cat.count}</div><div class="s sub">this month</div></div>
        <div class="kpi"><div class="k">Top category</div><div class="v">${top ? esc(top.key) : '—'}</div><div class="s sub num">${top ? inr(top.total) : 'nothing yet'}</div></div>
      </div>
      <div class="panel chart"><h3>Spending by day</h3>${barChart(dItems, {every: 5, avg, all: true, label: 'Spending by day'})}<div class="sub cap">Dashed line is your daily average.</div></div>
      <div class="grid2">
        <div class="panel"><h3>By category</h3>${cat.total > 0 ? donut(cat.groups, cat.total) : '<div class="empty">Nothing recorded this month.</div>'}</div>
        <div class="panel chart"><h3>Last 6 months</h3>${barChart(mItems, {highlight: 5, label: 'Spending over the last 6 months'})}</div>
      </div>
      <div class="panel" style="margin-top:20px"><div class="toolbar" style="margin:0 0 8px"><h3 style="margin:0">Latest this month</h3><button class="link" id="see-all">See all</button></div>
        ${recent.items.length ? recent.items.map(i => `<div class="lrow"><span class="num sub">${esc(i.date.slice(5))}</span><span>${esc(i.description || i.category)} <span class="tag">${esc(i.category)}</span></span><span class="num">${inr(i.amount)}</span></div>`).join('') : '<div class="empty">No expenses in this month.</div>'}</div>`;
    $('#see-all').onclick = () => { F.date_from = from; F.date_to = to; F.category = ''; S.page = 1; go('expenses'); };
  } catch (e) { $('#ov').innerHTML = `<div class="err">${esc(e.message)}</div>`; }
}

/* ---------- expenses ---------- */
const F = { date_from: '', date_to: '', category: '' };
S.opts = { categories: [], subcategories: {} };
async function loadOptions() { try { S.opts = await api('/api/expenses/options'); } catch {} }
const fmtD = d => new Date(d + 'T00:00:00').toLocaleDateString('en-IN', {day: 'numeric', month: 'short', year: '2-digit'});
function usageHtml(i) {
  const a = i.start_use_date, b = i.finished_on;
  if (a && b) { const days = Math.round((new Date(b) - new Date(a)) / 864e5) + 1; return `${fmtD(a)} → ${fmtD(b)}<div class="sub">${days} ${days === 1 ? 'day' : 'days'} in use</div>`; }
  if (a) return `In use since ${fmtD(a)}`;
  if (b) return `Finished ${fmtD(b)}`;
  return '<span class="sub">—</span>';
}

async function viewExpenses() {
  await loadOptions();
  $('#view').innerHTML = `
    <div class="toolbar"><h2>Expenses</h2><button class="primary" id="add">Add expense</button></div>
    <div class="filters">
      <div><label for="q-from">From</label><input id="q-from" type="date" value="${F.date_from}"></div>
      <div><label for="q-to">To</label><input id="q-to" type="date" value="${F.date_to}"></div>
      <div><label for="q-cat">Category</label><select id="q-cat"><option value="">All categories</option>${S.opts.categories.map(c => `<option ${c === F.category ? 'selected' : ''}>${esc(c)}</option>`).join('')}</select></div>
      <button id="q-go">Filter</button>
      <button id="q-clear">Clear filters</button>
    </div>
    <div class="err" id="x-err"></div><div id="list"></div>`;
  $('#add').onclick = () => openForm();
  $('#q-go').onclick = () => { F.date_from = $('#q-from').value; F.date_to = $('#q-to').value; F.category = $('#q-cat').value; S.page = 1; loadList(); };
  $('#q-clear').onclick = () => { F.date_from = F.date_to = F.category = ''; S.page = 1; viewExpenses(); };
  loadList();
}
async function loadList() {
  const p = new URLSearchParams({page: S.page, page_size: 15});
  Object.entries(F).forEach(([k, v]) => v && p.set(k, v));
  try {
    const d = await api('/api/expenses?' + p);
    S.rows = Object.fromEntries(d.items.map(i => [i.id, i]));
    const pages = Math.max(1, Math.ceil(d.total / d.page_size));
    $('#list').innerHTML = d.items.length ? `
      <div class="ledger"><table><thead><tr><th>Date</th><th>Category</th><th>Description</th><th>Usage</th><th class="r">Amount</th><th>Files</th><th></th></tr></thead><tbody>
      ${d.items.map(i => `<tr><td class="num">${esc(i.date)}</td>
        <td>${esc(i.category)}${i.subcategory ? `<div class="sub">${esc(i.subcategory)}</div>` : ''}</td>
        <td>${esc(i.description)} ${i.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</td>
        <td class="usage">${usageHtml(i)}</td>
        <td class="r num">${inr(i.amount)}</td><td class="num">${i.bill_ids.length || ''}</td>
        <td class="r"><button class="link" data-edit="${i.id}">Edit</button><button class="link danger" data-del="${i.id}">Delete</button></td></tr>`).join('')}
      </tbody></table></div>
      <div class="pager"><span>${d.total} total</span><span><button id="pv" ${S.page <= 1 ? 'disabled' : ''}>Previous</button> Page ${S.page} of ${pages} <button id="nx" ${S.page >= pages ? 'disabled' : ''}>Next</button></span></div>`
      : '<div class="panel empty">No expenses match. Add one, or clear the filters.</div>';
    $('#list').onclick = async e => {
      if (e.target.dataset.edit) openForm(S.rows[e.target.dataset.edit]);
      if (e.target.dataset.del && confirm('Delete this expense and its files?')) { await api('/api/expenses/' + e.target.dataset.del, {method:'DELETE'}); loadList(); }
      if (e.target.id === 'pv') { S.page--; loadList(); }
      if (e.target.id === 'nx') { S.page++; loadList(); }
    };
  } catch (e) { $('#x-err').textContent = e.message; }
}

/* ---------- expense form + attachments ---------- */
const refreshAfterSave = () => S.tab === 'expenses' ? loadList() : go(S.tab);
function fillSubs() {
  $('#subs').innerHTML = (S.opts.subcategories[$('#f-cat').value] || []).map(s => `<option value="${esc(s)}">`).join('');
}
async function openForm(exp = null) {
  S.editing = exp; $('#f-err').textContent = ''; $('#f-file').value = '';
  await loadOptions();
  const cats = [...S.opts.categories];
  if (exp && !cats.includes(exp.category)) cats.push(exp.category);   // older records with a custom category
  $('#dlg-title').textContent = exp ? 'Edit expense' : 'Add expense';
  $('#f-cat').innerHTML = '<option value="" disabled>Select category</option>' + cats.map(c => `<option>${esc(c)}</option>`).join('');
  $('#f-cat').value = exp?.category || '';
  $('#f-date').value = exp?.date || todayStr();
  $('#f-amount').value = exp?.amount ?? '';
  $('#f-sub').value = exp?.subcategory || '';
  $('#f-start').value = exp?.start_use_date || ''; $('#f-end').value = exp?.finished_on || '';
  $('#f-desc').value = exp?.description || ''; $('#f-tags').value = (exp?.tags || []).join(', ');
  fillSubs(); await renderBills(); $('#dlg').showModal();
}
$('#f-cat').onchange = fillSubs;

async function renderBills() {
  const box = $('#f-bills'); box.innerHTML = '';
  if (!S.editing) return;
  const bills = await api('/api/bills?expense_id=' + S.editing.id).catch(() => []);
  box.innerHTML = bills.map(b => `<div class="billrow"><span>${esc(b.filename)}</span><span>
    <button class="link" data-open="${b.id}" data-name="${esc(b.filename)}" data-ct="${esc(b.content_type)}">${/pdf|image/.test(b.content_type) ? 'View' : 'Download'}</button>
    <button class="link danger" data-rm="${b.id}">Remove</button></span></div>`).join('');
}
$('#f-bills').onclick = async e => {
  const t = e.target;
  if (t.dataset.open) {
    const viewable = /pdf|image/.test(t.dataset.ct);
    const w = viewable ? window.open('', '_blank') : null;
    try {
      const r = await api(`/api/bills/${t.dataset.open}/download`, {raw: true});
      const url = URL.createObjectURL(await r.blob());
      if (w) w.location = url;
      else { const a = document.createElement('a'); a.href = url; a.download = t.dataset.name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 10000); }
    } catch (x) { if (w) w.close(); $('#f-err').textContent = x.message; }
  }
  if (t.dataset.rm) { await api('/api/bills/' + t.dataset.rm, {method:'DELETE'}); renderBills(); refreshAfterSave(); }
};
$('#f-cancel').onclick = () => $('#dlg').close();
$('#f-save').onclick = async () => {
  $('#f-err').textContent = '';
  const body = {
    date: $('#f-date').value, amount: $('#f-amount').value, category: $('#f-cat').value,
    subcategory: $('#f-sub').value.trim() || null,
    start_use_date: $('#f-start').value || null, finished_on: $('#f-end').value || null,
    description: $('#f-desc').value, tags: $('#f-tags').value.split(','),
  };
  if (!body.category) { $('#f-err').textContent = 'Choose a category'; return; }
  try {
    const saved = await api(S.editing ? '/api/expenses/' + S.editing.id : '/api/expenses', {method: S.editing ? 'PUT' : 'POST', json: body});
    S.editing = saved;   // a retry now updates this expense instead of creating a duplicate
    const failed = [];
    for (const file of $('#f-file').files) {
      const fd = new FormData(); fd.append('file', file); fd.append('expense_id', saved.id);
      try { await api('/api/bills', {method: 'POST', form: fd}); } catch (e) { failed.push(`${file.name}: ${e.message}`); }
    }
    refreshAfterSave();
    if (failed.length) {
      $('#f-err').textContent = 'Expense saved, but some files were not uploaded. ' + failed.join(' | ');
      $('#f-file').value = ''; $('#dlg-title').textContent = 'Edit expense'; await renderBills(); return;
    }
    $('#dlg').close();
  } catch (e) { $('#f-err').textContent = e.message; }
};

/* ---------- assistant ---------- */
const SUGGEST = ['How much did I spend this month?', 'What are my top categories?', 'Show my last 5 expenses', 'Which expenses have bills attached?'];
function viewChat() {
  $('#view').innerHTML = `<h2>Assistant</h2><div class="chat"><div class="msgs" id="msgs"></div>
    <div class="chips">${SUGGEST.map(s => `<button data-q="${esc(s)}">${esc(s)}</button>`).join('')}</div>
    <div class="send"><input id="c-in" placeholder="Ask about your expenses" maxlength="500"><button class="primary" id="c-go">Ask</button></div></div>`;
  const draw = () => { $('#msgs').innerHTML = S.chat.length ? S.chat.map(m => `<div class="msg ${m.role === 'user' ? 'user' : 'bot'} ${m.pending ? 'pending' : ''}">${esc(m.content)}</div>`).join('') : '<div class="empty">Ask anything about your recorded expenses and bills. I only answer from your ledger.</div>'; $('#msgs').scrollTop = 1e9; };
  const ask = async q => {
    q = q.trim(); if (!q) return; $('#c-in').value = '';
    const history = S.chat.filter(m => !m.pending).map(({role, content}) => ({role, content}));
    S.chat.push({role:'user', content:q}, {role:'assistant', content:'Checking your ledger…', pending:true}); draw();
    let reply; try { reply = (await api('/api/chat', {method:'POST', json:{message:q, history}})).reply; } catch (e) { reply = e.message; }
    S.chat.pop(); S.chat.push({role:'assistant', content:reply}); draw();
  };
  $('#c-go').onclick = () => ask($('#c-in').value);
  $('#c-in').addEventListener('keydown', e => { if (e.key === 'Enter') ask(e.target.value); });
  document.querySelector('.chips').onclick = e => e.target.dataset.q && ask(e.target.dataset.q);
  draw();
}

boot();
