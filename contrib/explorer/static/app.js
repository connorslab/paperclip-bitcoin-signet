'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = value => new Intl.NumberFormat('en-US').format(value);
const coins = value => (value / 1e8).toFixed(8) + ' test BTC';
const short = hash => hash.slice(0, 12) + '…' + hash.slice(-8);
const bytes = n => n < 1000 ? `${n} B` : `${(n / 1000).toFixed(2)} kB`;
const stamp = n => new Date(n * 1000).toLocaleString(undefined, {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
const age = n => {const s = Math.max(0, Math.floor(Date.now()/1000-n)); return s < 60 ? `${s}s ago` : s < 3600 ? `${Math.floor(s/60)}m ago` : `${Math.floor(s/3600)}h ago`;};
const link = (kind, hash, label) => `<a class="mono" href="#${kind}/${esc(hash)}">${esc(label ?? short(hash))}</a>`;
const fee = t => t.coinbase ? '<span class="badge">Coinbase</span>' : t.fee === null ? 'Unavailable' : `${num(t.fee)} sats <span class="muted">· ${(t.fee/t.vsize).toFixed(2)} sat/vB</span>`;
let state = null, routeSerial = 0, polling = false;
async function get(path) {
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch('/signet/api/' + path, {signal:controller.signal, cache:'no-store'});
    const data = await response.json();
    if (!response.ok) {const error = new Error(data.error || 'Explorer unavailable'); error.status = response.status; throw error;}
    return data;
  } finally {clearTimeout(timer);}
}
function stats(s) {
  const indexing = s.indexed_height < s.node_height;
  $('connection').className = 'connection' + (s.delayed || indexing ? ' delayed' : '');
  $('connection').textContent = s.delayed ? 'Data delayed · last update ' + age(s.updated) : indexing ? `Indexing ${s.indexed_height} / ${s.node_height}` : '● Live · updated ' + age(s.updated);
  $('stats').innerHTML = [['Latest block', num(s.indexed_height)],['Unconfirmed', num(s.mempool_count)],['Transactions indexed', num(s.transactions)],['Target block time','60 <em>seconds</em>']].map(([label,value]) => `<div class="stat"><small>${label}</small><strong>${value}</strong></div>`).join('');
  document.querySelectorAll('[data-confirm-height]').forEach(el => {el.textContent = num(Math.max(0, s.indexed_height - Number(el.dataset.confirmHeight) + 1)) + ' confirmations';});
}
function txTable(txs) {
  return txs.length ? `<div class="panel table-wrap"><table><thead><tr><th>Transaction</th><th>Output total</th><th>Virtual size</th><th>Fee</th></tr></thead><tbody>${txs.map(t => `<tr><td>${link('tx',t.txid)}</td><td>${coins(t.total)}</td><td>${num(t.vsize)} vB</td><td>${fee(t)}</td></tr>`).join('')}</tbody></table></div>` : '<div class="panel empty">No transactions to show.</div>';
}
function blockTable(blocks) {
  return `<div class="panel table-wrap"><table><thead><tr><th>Height</th><th>Mined</th><th>Transactions</th><th>Size</th><th>Total fees</th></tr></thead><tbody>${blocks.map(b => `<tr><td><a href="#block/${b.height}">${num(b.height)}</a></td><td title="${esc(new Date(b.time*1000).toISOString())}">${esc(stamp(b.time))}</td><td>${num(b.tx_count)}</td><td>${bytes(b.size)}</td><td>${b.fees === null ? 'Unavailable' : num(b.fees) + ' sats'}</td></tr>`).join('')}</tbody></table></div>`;
}
async function home(before) {
  const blocks = await get('blocks' + (before ? '?before=' + before : ''));
  let html = '';
  if (!before) {
    html += `<div class="section-title"><h2>The chain, at a glance</h2><a href="#block/107" class="badge orange">Explore the covenant demo →</a></div><div class="strip"><a href="#pending" class="tile pending"><small>WAITING TO CONFIRM</small><strong>${num(state.mempool_count)} transactions</strong><span>${bytes(state.mempool_vsize)} virtual size</span></a>${blocks.slice(0,6).map(b => `<a href="#block/${b.height}" class="tile"><small>CONFIRMED BLOCK</small><strong>${num(b.height)}</strong><span>${num(b.tx_count)} tx · ${bytes(b.size)}</span><small>${age(b.time)}</small></a>`).join('')}</div>`;
  }
  html += `<div class="section-title"><h2>${before ? 'Block history' : 'Recent blocks'}</h2><small>Times shown in your local timezone</small></div>${blockTable(blocks)}<div class="pager"><a href="#">Latest blocks</a>${blocks.length && blocks.at(-1).height > 0 ? `<a href="#blocks/${blocks.at(-1).height}">Older blocks →</a>` : ''}</div>`;
  if (!before) {
    const txs = await get('mempool');
    html += `<div class="section-title"><h2>Unconfirmed transactions</h2><small>${state.mempool_count ? `${num(state.mempool_count)} waiting` : 'The mempool is clear'}</small></div>${txs.length ? txTable(txs.slice(0,8)) : '<div class="panel empty">No transactions waiting. New transactions will appear here before they are mined.</div>'}${txs.length > 8 ? '<div class="pager"><a href="#pending">View pending transactions →</a></div>' : ''}`;
  }
  return html;
}
function field(label,value) {return `<div><dt>${label}</dt><dd>${value}</dd></div>`;}
async function blockPage(id, offset=0) {
  const b = await get(`block/${id}?offset=${offset}`);
  document.title = `Block ${b.height} · Paperclip Signet`;
  return `<div class="section-title"><h2>Block ${num(b.height)}</h2><a href="#">← All blocks</a></div><div class="panel"><div class="detail-header"><span class="badge orange" data-confirm-height="${b.height}">${num(b.confirmations)} confirmations</span><div class="mono hash">${esc(b.hash)}</div></div><dl class="detail-grid">${field('Mined',esc(stamp(b.time)))}${field('Transactions',num(b.tx_count))}${field('Size / weight',`${bytes(b.size)} / ${num(b.weight)} WU`)}${field('Total fees',b.fees === null ? 'Unavailable' : num(b.fees)+' sats')}${field('Difficulty bits',`<span class="mono">${esc(b.bits)}</span>`)}${field('Merkle root',`<span class="mono hash">${esc(b.merkle_root)}</span>`)}</dl></div><div class="pager">${b.height ? `<a href="#block/${b.height-1}">← Previous block</a>` : '<span></span>'}${b.height < state.indexed_height ? `<a href="#block/${b.height+1}">Next block →</a>` : ''}</div><div class="section-title"><h2>Transactions</h2><small>${offset+1}–${Math.min(offset+25,b.tx_count)} of ${num(b.tx_count)}</small></div>${txTable(b.transactions)}<div class="pager">${offset ? `<a href="#block/${id}/${Math.max(0,offset-25)}">← Previous transactions</a>` : '<span></span>'}${offset+25 < b.tx_count ? `<a href="#block/${id}/${offset+25}">More transactions →</a>` : ''}</div>`;
}
async function txPage(id) {
  const t = await get('tx/' + id);
  document.title = `Transaction ${short(t.txid)} · Paperclip Signet`;
  const status = t.height === null ? '<span class="badge orange">Unconfirmed</span>' : `<span class="badge orange" data-confirm-height="${t.height}">${num(t.confirmations)} confirmations</span>`;
  const maturity = t.coinbase ? field('Coinbase maturity',t.confirmations >= 100 ? 'Spendable in the next block' : `${100-t.confirmations} more confirmations needed`) : '';
  const scripts = (script,witness=[]) => `<details><summary>Script & witness data</summary><pre>${esc(script || '(empty script)')}${witness.length ? '\n\nWitness stack:\n' + witness.map((w,i)=>`${i}: ${esc(w)}`).join('\n\n') : ''}</pre></details>`;
  const inputs = t.inputs.map((i,n) => `<div class="io-item"><span>INPUT ${n}</span>${i.coinbase ? '<strong>Newly generated test coins</strong>' : `${link('tx',i.txid)} <span class="muted">:${i.vout}</span><p class="mono hash">${esc(i.address || 'Script output')}</p><strong>${i.value === null ? 'Previous amount not indexed' : coins(i.value)}</strong>`}${scripts(i.script,i.witness)}</div>`).join('');
  const outputs = t.outputs.map(o => `<div class="io-item"><span>OUTPUT ${o.n} · ${esc(o.type || 'script')}</span><p class="mono hash">${esc(o.address || o.asm || 'Unspendable output')}</p><strong>${coins(o.value)}</strong>${scripts(o.script)}</div>`).join('');
  return `<div class="section-title"><h2>Transaction</h2><a href="#">← Explorer</a></div><div class="panel"><div class="detail-header">${status}${t.coinbase ? ' <span class="badge">Coinbase</span>' : ''}<div class="hash mono">${esc(t.txid)}</div></div><dl class="detail-grid">${field('Block',t.height === null ? 'Awaiting confirmation' : `<a href="#block/${t.height}">${num(t.height)}</a>`)}${field(t.height === null ? 'First seen' : 'Block time',esc(stamp(t.time)))}${field('Output total',coins(t.total))}${field('Fee',fee(t))}${field('Size / virtual size',`${bytes(t.size)} / ${num(t.vsize)} vB`)}${field('Version / locktime',`${t.version} / ${t.locktime}`)}${maturity}</dl></div><div class="section-title"><h2>Transaction flow</h2><small>Amounts in test BTC</small></div><div class="io"><article class="panel"><h3>${t.inputs.length} input${t.inputs.length === 1 ? '' : 's'}</h3>${inputs}</article><article class="panel"><h3>${t.outputs.length} output${t.outputs.length === 1 ? '' : 's'}</h3>${outputs}</article></div>`;
}
async function render() {
  const serial = ++routeSerial, route = location.hash.slice(1).split('/');
  try {
    if (!state) {state = await get('status'); stats(state);}
    let html;
    document.title = 'Paperclip · Bitcoin Signet Explorer';
    if (!route[0]) html = await home();
    else if (route[0] === 'blocks' && /^\d{1,10}$/.test(route[1])) html = await home(route[1]);
    else if (route[0] === 'block' && /^(\d{1,10}|[0-9a-f]{64})$/.test(route[1]) && (!route[2] || /^\d{1,6}$/.test(route[2]))) html = await blockPage(route[1],Number(route[2] || 0));
    else if (route[0] === 'tx' && /^[0-9a-f]{64}$/.test(route[1])) html = await txPage(route[1]);
    else if (route[0] === 'pending') html = `<div class="section-title"><h2>Unconfirmed transactions</h2><a href="#">← Explorer</a></div><p class="muted">Showing up to 200 transactions from the latest snapshot. Mempool contents can change before confirmation.</p><br>${txTable(await get('mempool'))}`;
    else throw new Error('Page not found. Search for a block height or transaction ID.');
    if (serial === routeSerial) $('content').innerHTML = html;
  } catch (error) {
    if (serial === routeSerial) $('content').innerHTML = `<div class="panel empty">${esc(error.name === 'AbortError' ? 'The explorer is taking longer than expected. Please try again.' : error.message)}<p><a href="#">Back to explorer</a></p></div>`;
  }
}
$('search').addEventListener('submit', async event => {
  event.preventDefault(); const q = $('query').value.trim().toLowerCase(); $('search-error').textContent = '';
  if (/^\d{1,10}$/.test(q)) {location.hash = 'block/' + q; return;}
  if (!/^[0-9a-f]{64}$/.test(q)) {$('search-error').textContent = 'Enter a block height or a 64-character block hash / transaction ID.'; return;}
  try {await get('block/' + q); location.hash = 'block/' + q;}
  catch (error) {if (error.status === 404) location.hash = 'tx/' + q; else $('search-error').textContent = 'Search is temporarily unavailable. Please try again.';}
});
function theme(mode) {document.documentElement.dataset.theme = mode; $('theme').textContent = mode === 'light' ? 'Dark mode' : 'Light mode';}
try {theme(localStorage.getItem('paperclip-explorer-theme') || 'dark');} catch {theme('dark');}
$('theme').onclick = () => {const mode = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'; theme(mode); try {localStorage.setItem('paperclip-explorer-theme',mode);} catch {}};
window.addEventListener('hashchange', () => {render();});
async function poll() {
  if (polling || document.hidden) return;
  polling = true;
  try {state = await get('status'); stats(state); if (!location.hash || location.hash === '#' || location.hash === '#pending') await render();}
  catch {$('connection').textContent = 'Connection unavailable · showing last loaded data'; $('connection').className = 'connection delayed';}
  finally {polling = false;}
}
render(); poll(); setInterval(poll,10000);
