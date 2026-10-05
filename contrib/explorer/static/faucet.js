'use strict';
const faucetForm = document.getElementById('faucet-form');
const faucetResult = document.getElementById('faucet-result');
faucetForm.addEventListener('submit', async event => {
  event.preventDefault();
  const address = document.getElementById('faucet-address').value.trim();
  const button = faucetForm.querySelector('button');
  let saved;
  try { saved = JSON.parse(sessionStorage.getItem('faucet-request')); } catch (_) {}
  const claim = saved && saved.address === address && !(saved.completedAt && Date.now() - saved.completedAt > 86400000)
    ? saved : {address, id: crypto.randomUUID()};
  try { sessionStorage.setItem('faucet-request', JSON.stringify(claim)); } catch (_) {}
  button.disabled = true;
  faucetResult.textContent = 'Requesting test coins…';
  try {
    const response = await fetch('/signet/api/faucet', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(claim), signal: AbortSignal.timeout(60000)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Faucet unavailable.');
    if (result.state === 'sent' && /^[a-f0-9]{64}$/.test(result.txid)) {
      if (!claim.completedAt) claim.completedAt = Date.now();
      try { sessionStorage.setItem('faucet-request', JSON.stringify(claim)); } catch (_) {}
      faucetResult.textContent = 'Sent 0.01 test BTC. ';
      const link = document.createElement('a');
      link.href = '/signet/#tx/' + result.txid;
      link.textContent = 'View transaction →';
      faucetResult.append(link);
    } else {
      faucetResult.textContent = 'Your request is recorded, but its payment needs verification. Check your wallet; do not submit another address. Reference: ' + claim.id;
    }
  } catch (error) {
    faucetResult.textContent = error.name === 'TimeoutError' || error.name === 'TypeError'
      ? 'Connection interrupted. Check your wallet, then retry this same address to check the original request.'
      : error.message;
  } finally { button.disabled = false; }
});
