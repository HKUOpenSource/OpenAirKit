# Next development round review — 2026-09-23

[简体中文](2026-09-23-next-round-review.zh-CN.md)

Source: `fd3b3b0`, branch `zhaolin/UI`, initially clean. Question: is the
current repository ready for further development, and which defects and
acceptance gaps should be addressed first? No `.codegraph/` directory exists;
architecture, entry points, selected source paths and tests were read directly.
This is a review record; [the roadmap](../roadmap.md) remains the task authority.

## Findings

1. **P1 — Management protection does not verify the tunnel transport.**
   `network.inspect_management` checks that Wi-Fi has one address and that the
   Spark destination routes through the configured Tailscale interface. It does
   not check whether the tunnel itself uses Wi-Fi or the experimental RNDIS
   path. `Network.snapshot -> Agent.auto_reconcile/Agent.write -> modem.write`
   trusts this result before permitting recovery and modem writes. If Tailscale
   uses the data path, a modem reset can interrupt management despite
   `management_protected=true`. A mocked reproduction returned true after only
   one route lookup, for the overlay destination. The earlier
   [hardware record](2026-09-23-connectivity-only.md) also documents Tailscale
   preferring the experimental path and using a separate Wi-Fi management path
   during recovery tests. This review did not measure the current tunnel path
   or cause an outage. Before disruptive acceptance, establish and verify a
   management path independent of the modem; reject disruptive writes when
   that independence cannot be established. Add coverage for a valid overlay
   route whose underlying transport uses RNDIS, plus changing/unavailable paths.

2. **P2 — Passive rates span different interfaces.**
   `Network.snapshot` retains only `(time, counters)` in `self.previous`.
   `Agent.sample -> Network.snapshot -> rx_bps/tx_bps` therefore subtracts the
   old interface's counters from the new interface's counters after device
   rediscovery. A mocked switch from `rndis0` to `rndis1`, with counters changing
   from 1,000 to 1,000,000 bytes over one second, reported 7,992,000 bps on both
   directions. The first sample of a new interface should be unavailable.
   Track interface identity/generation and invalidate the baseline after
   discovery failure, replacement or counter reset. Cover replacement with
   larger counters, disappearance/reappearance and normal same-interface deltas.

## Current device baseline

Read-only SSH inspection used public loopback health endpoints, selected
systemd properties, release metadata, file hashes and USB/container inventory.
No installation, restart, modem command, route change or fault injection ran.

| Item | Spark | Jetson |
| --- | --- | --- |
| OS / architecture | Ubuntu 24.04.4 / aarch64 | Ubuntu 22.04.5 / aarch64 |
| Python | 3.12.3 | 3.10.12 |
| Application version | 0.1.0 | 0.4.0 |
| Installed release | `d987aca4396311d2` | `0826938fd08ae477` |
| Health | status/collector `ok` | status/web/device `ok` |
| Application services | Three active, disabled at boot, zero restarts | Two V2 services active, disabled at boot, zero restarts |
| Hardware | USRP B210 | Quectel RM520N-GL |

Spark radio was active and all 12 project Open5GS/data-network containers were
healthy. Jetson's two retired services remained failed and disabled; this does
not indicate failure of the active V2 services.

Both release manifests identify base revision `3ae3d76` and `dirty=true`.
SHA-256 comparisons matched current source for Jetson `agent.py`, `network.py`
and `deploy/jetson/manage.py`, and Spark `web.py` and `collector.py`. These five
matches do not establish whole-package equivalence or replace clean-source
release provenance. No fresh authenticated UE registration/PDU/user-plane
acceptance was performed; health and container status cannot prove connectivity.

## Verification

- `make check VENV=local/bootstrap-check`: passed under Python 3.11.15.
  Jetson: 46 passed; Spark: 51 discovered, 50 passed and one existing macOS
  peer-credential skip; shared stack/release tests: 102 passed. TypeScript,
  documentation, release, license and shell audits passed.
- The first sandboxed run failed because a shared test could not bind localhost.
  The complete rerun with loopback permission passed; no test was weakened.
- Both frontend `npm run build` commands passed.
- `make e2e-jetson e2e-spark VENV=local/bootstrap-check`: passed; Jetson's
  four-page suite and all three Spark browser suites used isolated synthetic
  services. This is browser evidence, not hardware evidence.
- Both findings were reproduced with in-memory mocks, without device access.
- Local Node was 24.14.0, while the documented/CI version is 22. The default
  `.venv` remains Python 3.9.6; use the explicit environment above. This round
  did not rerun the native Python 3.10/3.12 matrix or Node 22 CI, create release
  archives, or test installation/rollback.

## Suggested next sequence

First address management-path verification and interface-generation accounting,
then complete the remaining P3-15 simulator and hardware fault cases. Build
artifacts from a clean revision and reconcile existing installation/rollback
evidence with R06 and P3-16 before deciding which checks need repetition.
Complete the precise P3-17 stop/start, reconnection and single-controller
criteria with independent management reachability. Prior radio cycles do not
prove forced modem reset behavior or automatic retry-budget exhaustion.

Preserve the current connectivity-only scope: small diagnostics and passive
counters remain; active throughput features stay retired. Historical throughput
records are not new acceptance requirements. Leave P3-GATE open until the
remaining evidence is complete. This review changes documentation only and
does not mark any roadmap item complete.

## P2 source fix follow-up

Question: can passive rates survive interface changes without combining unrelated
counters? The follow-up changes `Agent.sample -> Network.snapshot -> rx_bps/tx_bps`:
the baseline now includes interface name and kernel ifindex, and is cleared when
discovery or counter reads fail. Identity changes and decreasing counters start
a new interval with unavailable rates. The ifindex is checked before and after
reading counters to reject replacement during sampling. Elapsed time uses a
monotonic clock; observation timestamps remain wall-clock timestamps.

Seven regression tests cover normal deltas, rename/replacement (including reuse
of the same name), discovery failure, counter-read failure, counter reset,
replacement during sampling and wall-clock adjustment. Before the fix, targeted
tests reproduced the invalid cross-interface rates and retained failure baseline.
After the fix, all 53 Jetson backend tests pass. The change affects passive
observation only; no device deployment or hardware acceptance was performed.
