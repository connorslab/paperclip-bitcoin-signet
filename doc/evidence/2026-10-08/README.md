# Template-only CSFS: live signet application tests

The three-party lifecycle passed on October 8, 2026, after activation at height 3250.
Ark completed one refresh and recovery; the planned two-refresh run did not complete.
They demonstrate compatibility of specific experimental spending paths with the
fixed 32-byte, current-input-template-only CSFS rule. They do not establish that
the proposal is ready for production activation or eliminates all data storage.

## Ark: offline refresh and independent exit

- One 100,000-test-sat allocation and two preauthorized refreshes; only the first completed.
- Separate native ASP and watchman processes. No wallet commands between
  2026-10-08T15:32:42.891859+00:00 and 2026-10-08T15:50:08.327563+00:00.
- ASP funded one replacement; watchman recovered from a stale unroll using
  the first permit with ASP stopped. Watchman restart preserved the signed transactions.
- With both services stopped, the owner recovered **98,000 test sats** after
  the timelock. Premature recovery was rejected before the final valid spend.
- Allocation reduced by 1,000 sats for the completed refresh and 1,000 for the final claim.
  Other funding, unroll and refund costs are additional test expenses.

This is the opt-in single-balance covenant-service experiment, not the ordinary
Ark boarding/database/API path. One operator controlled the test environment.
Wallet inactivity is a harness property, not physical isolation from that operator.
Expiry limits, backups, monitoring and fee funding still matter.

The initial remote-RPC harness was interrupted because startup history scanning
was slow. The same signed journal and service code were resumed beside the
signet node using its system ELF loader. Debug metadata was stripped to reduce
transfer size; loadable runtime sections were compared byte-for-byte before use.
Executed file hashes are recorded separately from the original debug binaries. No replacement
funding or authorizations were regenerated. The delay crossed the second funding cutoff, so that round was not funded.
The originally planned two-refresh case is explicitly incomplete. This limitation is not
a consensus rejection; it reinforces that the observer is an experimental one.

## Three-party channel: stale state, override and settlement

- Three separate participant signing processes approved and saved two updates:
  100,000/100,000/100,000 → 95,000/100,000/105,000 → 95,000/103,000/102,000 sats.
- The older update was deliberately confirmed, then superseded by the latest
  pre-signed update. No fresh participant signatures were requested for recovery.
- A read-only mempool check rejected premature settlement as `non-BIP68-final`.
- After the 12-block contest delay, settlement confirmed with outputs of
  **95,000, 103,000 and 102,000 test sats**, matching the final agreement.

This is an experimental three-party contest channel, **not a BOLT-compatible
Lightning channel**. It does not test invoice routing, HTLCs, independent hostile
operators, production fee bumping or a public exchange-point service.

## Confirmed public transactions

| Experiment / step | Height | vbytes | Fee (test sats) | Transaction |
| --- | ---: | ---: | ---: | --- |
| Ark / dedicated test reserve | 4120 | 225 | 225 | [0f077123d0b3…](https://node2.paperclippool.xyz/signet/#tx/0f077123d0b31178790dde1218bfd07a630ddd37545e94683418a57c00243437) |
| Ark / original backing | 4121 | 234 | 234 | [abf2a38c5dfd…](https://node2.paperclippool.xyz/signet/#tx/abf2a38c5dfd14322ac56e875214523238480a396c5c2f0064df038fb3cd96b7) |
| Ark / stale user unroll | 4138 | 121 | 1000 | [fb3d1118b68a…](https://node2.paperclippool.xyz/signet/#tx/fb3d1118b68a0c601994283f0f22f26a2f70f5a86587f64bc476b051efced234) |
| Ark / round 1 funding | 4135 | 234 | 234 | [acb6834199ab…](https://node2.paperclippool.xyz/signet/#tx/acb6834199ab8a1de9b6284ebd50f622cdee129e7a8425edbaf5f65fffae5856) |
| Ark / round 1 unroll | 4138 | 121 | 1000 | [71d672d3db7f…](https://node2.paperclippool.xyz/signet/#tx/71d672d3db7f73d32026e9a708af51925dca11b9b3b04d9366edeeb7059c4fda) |
| Ark / round 1 refund | 4138 | 313 | 1000 | [5002c4a5a13e…](https://node2.paperclippool.xyz/signet/#tx/5002c4a5a13edb049409668bcd71bd8b463f684cd56b5306d5af74f1451ff92b) |
| Ark / independent user recovery | 4145 | 126 | 1000 | [751ee901c5eb…](https://node2.paperclippool.xyz/signet/#tx/751ee901c5eb8655d79396299059be54696f629bfcfe9e19c1bea4f650fa2fb8) |
| Three-party / funding | 4120 | 218 | 218 | [59d9b86d6ce8…](https://node2.paperclippool.xyz/signet/#tx/59d9b86d6ce83af69403aa72219a34835cfc70c1c71c8293862002dcde07d4d0) |
| Three-party / stale | 4121 | 257 | 1000 | [15c248b1cf7f…](https://node2.paperclippool.xyz/signet/#tx/15c248b1cf7f67426da330ad1df28b73e8aa359e7ff3e58706d9c230afa587ee) |
| Three-party / override | 4122 | 257 | 2000 | [34d00abecc4a…](https://node2.paperclippool.xyz/signet/#tx/34d00abecc4ac55ef42dc523c68aba78a51799cbaec3239fe3142d2497e0b599) |
| Three-party / settlement | 4134 | 171 | 1000 | [ff5d4a20351a…](https://node2.paperclippool.xyz/signet/#tx/ff5d4a20351a33f431e4919325b4380f1ba81ac6ce0dbf254ed2ec472453a808) |

## Provenance and verification

- Node implementation: `8b0c84ea587189af4bb3a97faea21845b77fb83d`, release v0.2.0-bitcoin-signet.
- Live bitcoind SHA256: `1e586a18863badd1d5205ca32704fb5b1383287d03a4727a52fe6912547102bb`.
- Ark source: [ASP experimental branch](https://github.com/connorslab/paperclip-asp/tree/experiment/covenant-offline-refresh)
  and [wallet experimental branch](https://github.com/connorslab/paperclip-wallet-app/tree/experiment/covenant-offline-refresh).
  Tested binaries originate from ASP `bd67f1d` and wallet `2409e284457f68ae3b80871dd0acb5f080568ab7`;
  their original and executed SHA256 hashes are in the results.
- Three-party implementation: [source](https://github.com/connorslab/paperclip-lightning-signet/tree/1aac9c8fef1cd0e62341afe1d7a8e8141d075d02).
  Channel, participant and signet driver source blobs matched the published repository.
- [Ark results](ark-results.json), [channel results](channel-results.json),
  [public explorer transaction observations](transactions.json).
- The explorer indexes the same node: these are cross-checks, not independent
  consensus validation. Reorgs can change confirmation status after observation.
- No node restart, forced blocks, chain reset, mainnet funds or public invalid
  transaction broadcasts. Test keys and runtime journals remain private.
- Existing private tests additionally covered unrelated CSFS messages, boundary
  lengths, activation history and crash/reorg recovery. Those are **regtest**
  results, distinct from the confirmed live transactions above.

## Before production activation

These are compatibility evidence, not an activation recommendation. Independent
implementation review, broader adversarial and resource-limit tests, protocol
recovery analysis and an agreed deployment/migration plan remain necessary.
