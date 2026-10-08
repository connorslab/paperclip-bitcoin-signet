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
  document.querySelectorAll('.flow-card').forEach(card => {
    card.classList.remove('updated');
    void card.offsetWidth;
    card.classList.add('updated');
  });
}));

// Finite, user-triggered walkthrough. No continuously moving or hidden content.
const arkSteps = Array.from(document.querySelectorAll('.ark-diagram > div'));
const arkCopy = [
  '1 / The wallet prepares and signs the permitted future refresh while the user is online.',
  '2 / The service carries out that permitted refresh while the wallet is offline. It cannot substitute a different covered output and keep the same valid signature.',
  '3 / The user needs recovery data, fee funding and time to exit independently. This is a separate recovery path, not a forced withdrawal after every refresh.'
];
const arkPlay = document.getElementById('ark-play');
let arkTimer;
let arkStep = 0;
function showArkStep(step) {
  arkSteps.forEach((card, i) => card.classList.toggle('active-step', i === step));
  document.getElementById('ark-explanation').textContent = arkCopy[step];
}
showArkStep(0);
arkPlay.addEventListener('click', () => {
  if (arkTimer) {
    clearTimeout(arkTimer);
    arkTimer = undefined;
    arkPlay.textContent = 'Replay the refresh walkthrough';
    return;
  }
  arkStep = 0;
  showArkStep(arkStep);
  arkPlay.textContent = 'Pause walkthrough';
  function advance() {
    showArkStep(++arkStep);
    if (arkStep < arkCopy.length - 1) arkTimer = setTimeout(advance, 5500);
    else { arkTimer = undefined; arkPlay.textContent = 'Replay the refresh walkthrough'; }
  }
  arkTimer = setTimeout(advance, 5500);
});
if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('reveal-once');
      observer.unobserve(entry.target);
    }
  }), { threshold: 0.08 });
  document.querySelectorAll('.plain-grid article, .opcode-card, .comparison-art article, .usecase').forEach(card => observer.observe(card));
}
