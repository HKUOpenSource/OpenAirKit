# Development readiness review — 2026-09-27

[简体中文](2026-09-27-development-readiness.zh-CN.md)

Reviewed source: `39dde4d0216dee973ed6cbf40ecb500e83c1ac74`, branch `main`,
initially clean. Local development checks pass. Hardware acceptance requires
resolving resource ownership and management-path protection first. This targeted
review does not close any gate; [the roadmap](../roadmap.md) remains the only
completion checklist.

## Question, scope and method

Question: what is the current repository/device baseline and the next development
order? No `.codegraph/` index exists. Direct inspection covered architecture,
roadmap, recent acceptance records, CI, network protection and lifecycle scripts.
SSH checks read service properties, USB inventory, project-scoped container state,
loopback health, selected process identity/port arguments and release hashes.
The installed lifecycle `status` commands also acquire their normal user-level
lock. No service start/stop, deployment, modem write, route change or fault injection
ran. Addresses, credentials and raw operational logs are omitted.

## Findings and development order

1. **P1 — Startup does not reject an already occupied web port before mutations.**
   Both Agentic-OCUDU platforms are stopped, but another installed platform serves
   their configured ports. Spark `oai-spark-web.service` is active and enabled,
   with its MainPID's command selecting port 8877; `oai-spark-collector.service`
   is also active. Jetson `oai-console.service` is active and enabled, with its
   MainPID selecting port 8878. These are separate from the stopped project units.
   The path `start.sh → Controller.preflight → Controller.start → maintain`
   does not check listener ownership before starting services. Spark can start
   core and radio before discovering the web conflict; Jetson can request device
   startup before web readiness fails. In an isolated mock with a pre-existing
   listener and an injected application-start failure, Spark requested
   `core-start`, `radio-start`, `start`; Jetson requested `start`. Both made zero
   listener checks. This is a mock reproduction, not a live startup attempt.
   Add a pre-mutation port/resource ownership check, explicit conflict output
   and regressions asserting zero mutations for a foreign listener, while
   retaining idempotent startup of the owned healthy service. Resolve site
   ownership before hardware acceptance; do not stop another platform implicitly.

2. **P1 — Management protection still does not verify the tunnel transport.**
   `network.inspect_management` verifies a Wi-Fi address and the route to Spark
   through the overlay, but not whether the overlay transport uses the modem.
   The path is `Agent.auto_reconcile → recovery → Agent.write → Network.snapshot
   → inspect_management → modem.write`, plus `helper(protect) → inspect_management`.
   A fresh mock returns `management_protected=true` with only one overlay route
   lookup. A disruptive modem write can therefore break management when transport
   depends on RNDIS. Current transport was not independently established here.
   Verify independent management transport and reject writes when evidence is
   absent, stale or changes. Cover RNDIS transport, valid independent transport,
   unavailable evidence and path changes before disruptive fault testing.

3. **Release provenance and Jetson acceptance remain incomplete.**
   Installed manifests still record base `fd3b3b0` and `dirty=true`. File hashes
   match their manifests, which proves listed-file integrity, not equivalence to
   clean current source. Build the next release from a clean revision; reconcile
   existing installation/rollback records with P3-16/R06 and execute missing
   checks. Complete P3-15's fault matrix and P3-17's exact five stop/start,
   reconnection and single-controller cycles before P3-GATE. The September 24
   lifecycle record covers one cycle, not five. Automatic CI covers Python 3.12 /
   Node 22; the Python 3.10/3.12 and browser matrix is manual. Preserve the current
   passive-traffic/small-diagnostic scope.

## Device baseline

| Item | Spark | Jetson |
| --- | --- | --- |
| SSH / architecture / Python | Reachable / aarch64 / 3.12.3 | Reachable / aarch64 / 3.10.12 |
| Installed application | 0.2.0 | 0.5.1 |
| Current release link | `5bc68497243efdf5` | `186b6c4659cc5e14` |
| Project services | Three monitor units, V2 core and radio inactive; PIDs zero | Both V2 units inactive; PIDs zero |
| Boot policy | Monitor disabled; core/radio static | V2 units disabled |
| Project runtime | No project core containers | Device socket absent |
| Listed manifest files | 28/28 match | 48/48 match |
| USB hardware | B210 detected | RM520N-GL detected |
| Root storage available | Approximately 2.8 TB | Approximately 189 GB |

The public health responses on the occupied ports are Spark
`status=ok, version=0.2.0, collector=available` and Jetson
`status=ok, version=0.3.0`. They belong to the other running platform and do not
establish Agentic-OCUDU health or UE connectivity. No fresh project registration,
PDU, RAN or user-plane acceptance is available in this stopped state. Jetson's
two retired `aoc-jetson-*` units remain failed and disabled, separately from V2.

Manifest SHA-256 values remain:

- Spark: `d37822fdad93c2c5fe842411b32b2de348fefd7d218d3e8f4e01afcf83634a9e`.
- Jetson: `6757bdcdafcc5fc73b1bbd7d4395d7c05bbc209f8248f53c5bcb96806288be37`.

All six installed operator scripts match the SHA-256 values in the
[September 24 lifecycle record](2026-09-24-platform-lifecycle.md).

## Validation and limits

`make check VENV=local/bootstrap-check` passed: Jetson 58; Spark 52 with one
existing macOS peer-credential skip; shared stack/release/lifecycle 134. Total:
244 passed, one skipped. TypeScript and documentation, release-boundary, license
and shell audits passed. The first sandboxed attempt failed only because a
shared HTTP test could not bind localhost; the full run with loopback permission
passed without changing tests. Both findings above also have isolated mock
reproductions on the reviewed revision.

Local validation used Python 3.11.15 and Node 24.14.0, with existing dependencies
and frontend build artifacts. This round did not rerun production builds,
browser E2E, the target interpreter matrix, release packaging or hardware
installation/rollback. The previous records remain historical evidence only.
Use the explicit environment above for development; it does not certify the
release matrix. Documentation changes update the review links and distinguish
installed versions from running services; application behavior is unchanged.
