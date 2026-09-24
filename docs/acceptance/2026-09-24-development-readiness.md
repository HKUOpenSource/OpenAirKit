# Development readiness review — 2026-09-24

[简体中文](2026-09-24-development-readiness.zh-CN.md)

Reviewed source: `dba599c830f2abe6a09309ca85a52afd281519cf`, branch `main`,
initially clean. The repository is ready for local development. Disruptive
Jetson acceptance should first address the management-path protection finding
below. This record does not close any gate; [the roadmap](../roadmap.md) remains
the only task checklist.

## Scope and method

Question: what is the current source/device baseline, and what should the next
development round address? No `.codegraph/` directory exists. Direct inspection
covered architecture, roadmap, recent acceptance records, CI/build/test entry
points, Jetson network/recovery/API paths and restricted maintenance status.
This is a targeted readiness review, not an exhaustive source or security audit.

Device inspection used read-only SSH, systemd properties, USB/container inventory,
loopback health endpoints, installed manifest hashes and the existing restricted
`aoc-maintain ue-status` action. No deployment, service restart, modem write,
route change or fault injection ran. Private addresses and raw logs are omitted.

## Findings and next development order

1. **P1 — Management protection still does not establish transport independence.**
   `apps/jetson-console/backend/aoc_jetson/network.py:82–99` checks a Wi-Fi
   address and the overlay route to Spark. It does not check whether Tailscale's
   underlying transport uses Wi-Fi or the modem data path. The call paths are
   `Agent.auto_reconcile → recovery job → Agent.write → Network.snapshot →
   inspect_management → modem.write` and `helper(protect) → inspect_management`.
   A mocked reproduction on this revision returned `management_protected=true`
   after exactly one route query, for the overlay destination. A reconnect could
   therefore disrupt management when the overlay depends on RNDIS. This review
   did not establish the current tunnel transport or cause an outage. Implement
   evidence of an independent management transport and reject disruptive writes
   when that evidence is missing, stale or changes. Add regressions for an overlay
   over RNDIS, valid independent transport, unavailable evidence and path changes
   before continuing disruptive hardware acceptance. This confirms the open
   finding in the [previous review](2026-09-23-next-round-review.md).

2. **Release evidence needs reconciliation with the current revision.**
   Both installed manifests record base `fd3b3b0` and `dirty=true`. All listed
   files match their installed manifest, but that establishes package integrity,
   not equivalence to clean `dba599c`. Existing
   [Astryx deployment](2026-09-23-astryx-deployment.md) and
   [Jetson 0.5.1 deployment](2026-09-23-jetson-live-stream.md) records already
   include rollback and reinstallation. Map those results to P3-16/R06 before
   repeating checks. Build the next candidate from a clean revision, run the
   target-version/browser release checks, record backups and manifest hashes,
   then complete missing installation, rollback and management-preservation
   evidence. This round neither builds release archives nor repeats deployment.

3. **Finish the remaining Jetson acceptance criteria.**
   P3-15 needs the complete simulator/hardware fault matrix, P3-17 needs exactly
   five stop/start/reconnection cycles with one modem controller, and P3-GATE
   remains open. Prior radio cycles and ordinary healthy status do not establish
   those conditions. Automatic recovery is currently paused; account for that
   explicitly when designing recovery acceptance. Preserve the current scope of
   passive counters and small diagnostics; active throughput tasks remain retired.

The previous P2 passive-rate finding is fixed in current source:
`Agent.sample → Network.snapshot` tracks interface name/ifindex, clears failed
baselines and uses monotonic elapsed time. Its seven regression tests pass.
README versions and roadmap version prose were stale; this review updates them
to Jetson 0.5.1 / Spark 0.2.0 and points the documentation index here, without
changing roadmap completion states or application behavior.

## Observed device baseline

| Item | Spark | Jetson |
| --- | --- | --- |
| Architecture / Python | aarch64 / 3.12.3 | aarch64 / 3.10.12 |
| Application | 0.2.0 | 0.5.1 |
| Active release | `5bc68497243efdf5` | `186b6c4659cc5e14` |
| Public health | status/collector `ok` | status/web/device `ok` |
| Application services | Three active, zero restarts | Two V2 services active, zero restarts |
| Boot policy / listener | Disabled / `127.0.0.1:8877` | Disabled / `127.0.0.1:8878` |
| Manifest file hashes | 28/28 match | 48/48 match |
| Hardware | USRP B210 detected | Quectel RM520N-GL detected |
| Root storage available | Approximately 2.8 TB | Approximately 192 GB |

Spark radio is active; all 12 project core/data-network containers report healthy.
Other containers also run on Spark. Jetson's two retired units remain failed and
disabled, separate from its healthy V2 units. The restricted Jetson status reports
fresh `quality=ok`, registration, active data PDU, matching lab policy and verified
RNDIS-bound data connectivity; `maintenance=false`, `recovery_paused=true`.
Its `management_protected=true` field retains the limitation described above.
This is the running executor's status, not a new independently correlated
Spark/Jetson end-to-end acceptance run or an authenticated browser inspection.

Manifest SHA-256:

- Spark: `d37822fdad93c2c5fe842411b32b2de348fefd7d218d3e8f4e01afcf83634a9e`.
- Jetson: `6757bdcdafcc5fc73b1bbd7d4395d7c05bbc209f8248f53c5bcb96806288be37`.

## Local validation and limits

- `make ci VENV=local/bootstrap-check`: passed. Jetson 58 passed; Spark 52
  passed and one macOS peer-credential skip; shared stack/release 102 passed.
  Both production frontend builds, TypeScript and documentation/release/license/
  shell audits passed. Vite retains the existing over-500-kB chunk advisories.
- The first `make check` attempt stopped at a shared test because the sandbox
  blocked binding localhost. The complete CI run with loopback permission passed;
  no test was changed or weakened.
- `make e2e-jetson e2e-spark VENV=local/bootstrap-check`: passed. Jetson's
  browser suite reported no failures; all three Spark suites passed, including
  desktop/mobile layouts, stale evidence, stream loss and authentication expiry.
  These checks use isolated synthetic services and are not hardware evidence.
- After the documentation updates, `make docs-audit VENV=local/bootstrap-check`
  passed for all 80 current documents, and `git diff --check` passed.
- The default `.venv` is Python 3.9.6 and is unsupported. The explicit environment
  above uses Python 3.11.15. Local Node is 24.14.0; CI specifies Node 22. This
  round does not certify the native Python 3.10/3.12 matrix or Node 22 behavior.
  Spark's system Node 18 is not a validation of its frontend build environment;
  deployed frontend assets are prebuilt.

The documentation changes record the question, affected call paths, operational
impact and tests. No production configuration or connection addresses are added.
