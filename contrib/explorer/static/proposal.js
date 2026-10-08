'use strict';
const themeButton = document.getElementById('theme');
function setTheme(mode) {
  document.documentElement.dataset.theme = mode;
  themeButton.textContent = mode === 'light' ? 'Dark mode' : 'Light mode';
}
try { setTheme(localStorage.getItem('paperclip-explorer-theme') === 'light' ? 'light' : 'dark'); }
catch { setTheme('dark'); }
themeButton.addEventListener('click', () => {
  const mode = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  setTheme(mode);
  try { localStorage.setItem('paperclip-explorer-theme', mode); } catch {}
});
const cases = {
  original: ['Outpoint A', '100,000 sats to Alice', 'Commitment A', 'The authorized template matches. The transaction still needs all other required checks.'],
  amount: ['Outpoint A', '90,000 sats to Alice', 'Commitment B', 'Changing the output changes the template hash. The original authorization no longer verifies.'],
  funding: ['Outpoint B', '100,000 sats to Alice', 'Commitment A', 'Changing only the input outpoint leaves the template hash unchanged. This enables rebinding; funding and other signature checks still apply.']
};
document.querySelectorAll('[data-case]').forEach(button => button.addEventListener('click', () => {
  const values = cases[button.dataset.case];
  if (!values) return;
  document.querySelectorAll('[data-case]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
  ['demo-input', 'demo-output', 'demo-hash', 'demo-result'].forEach((id, i) => { document.getElementById(id).textContent = values[i]; });
  document.getElementById('demo-result').classList.toggle('changed', button.dataset.case !== 'original');
}));
