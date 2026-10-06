# Configurable CSFS message policy

`-maxcsfsmsgsize=<n>` limits the number of message bytes consumed by each
executed experimental `OP_CHECKSIGFROMSTACK`. It applies only when CSFS is
active through `-xbtcovtest` on the experimental signet or private regtest.
It does not activate opcodes on any other network.

```ini
# bitcoin.conf; restart the node to apply
maxcsfsmsgsize=32
```

| Value | Meaning |
| --- | --- |
| `-1` (default) | No additional CSFS message cap |
| `0` | Only empty messages |
| `32` | Messages up to 32 bytes, including TEMPLATEHASH results |
| `1` through `520` | Explicit maximum message length in bytes |

Malformed values and values outside this range fail startup. A limit does
not relax the existing RDTS stack-element limit or standard witness-element
limits. Disabling this cap does not disable those other restrictions.

## What it enforces

Transactions exceeding the cap are rejected from the local mempool with
`csfs-message-size`, including via `testmempoolaccept`, `sendrawtransaction`
and peer admission. They therefore are not relayed or selected for normal
local block templates. Mempool reload and reorg re-admission use the same
policy. Other nodes may use different limits and mine these transactions;
otherwise-valid blocks are still accepted by this node.

The check inspects the actual message on the execution stack. It handles
witness arguments, script literals and computed messages, rather than
guessing from script bytes. It applies even when the CSFS signature is
empty. Ordinary consensus checkers impose no additional CSFS message limit.

An uncached policy-only script pass runs after normal script verification
when the cap is enabled. It uses the existing transaction signature checker
and signature cache but never caches its policy result in the consensus
script-execution cache. A previous successful block or script-cache entry
cannot bypass the cap. This adds script execution work for capped nodes;
there is no additional pass with the default disabled setting.

## Scope and tradeoffs

This is a per-message size policy, not a total transaction-data budget or
a data-storage prevention mechanism. It does not reduce signature or public
key sizes, count CSFS executions, identify meaningful messages, restrict
other data-carrying script paths, or limit a preimage that a script hashes
before CSFS. For example, an 80-byte witness item hashed with `OP_SHA256`
produces a 32-byte message and passes a 32-byte cap, subject to all other
rules. Multiple individually compliant messages also remain possible.

The current TEMPLATEHASH/CSFS design verifies a 32-byte digest and remains
compatible with a 32-byte cap. Applications signing longer messages directly
must use a compatible local policy or a separately designed commitment
protocol. Merely hashing messages requires agreement by signers and scripts;
it cannot transparently preserve an existing signature over raw data.

The setting makes no consensus change and requires no network activation.
It is not a guarantee that miners elsewhere follow the same policy, and it
does not provide application replay protection. Do not deploy experimental
covenants with real funds based on this filter.

## Reproducible validation

Build the node and unit tests, then run from the source root:

```sh
build/bin/test_bitcoin --run_test=script_tests
python3 test/functional/mempool_csfs_policy.py --configfile=build/test/config.ini
python3 test/functional/feature_xbt_covenants.py --configfile=build/test/config.ini
```

The new private-regtest test covers witness and script message boundaries,
zero/disabled/maximum settings, malformed startup values, a TEMPLATEHASH
spend, hashing a larger preimage, repeated validation, mempool and block
template rejection, acceptance of an over-cap transaction inside a valid
block, reorg re-admission, and restart. Unit coverage applies the cap to
valid BIP340 vectors, including empty and longer messages, and checks that
checker wrappers preserve it. Tests use disposable local chains only.

### Validation results — October 5, 2026

- Native Linux Release build completed on Flynn.
- All 19 selected script, sighash, signet, proof-of-work and validation unit
  suites passed, including the new CSFS policy vectors.
- `mempool_csfs_policy.py` passed on a two-node private regtest chain. This
  also covers empty signatures, multiple individually compliant CSFS calls,
  and dropping a previously permitted transaction during mempool reload
  after lowering the cap.
- Existing covenant, RDTS and unified-sighash functional tests passed.
- The signed-signet functional test passed standalone with exit status 0.
  The combined runner marked it failed because the existing imported signet
  miner emits logging to stderr; its assertions passed. This logging issue
  was not changed as part of the policy patch.

No live signet or production service was restarted or reconfigured. These
are native local test results, not a claim of a completed GitHub CI run.
