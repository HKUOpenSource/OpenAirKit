# Spark Console Operations

[简体中文](spark-operations.zh-CN.md)

This guide covers daily Web Console workflows, unified full-stack lifecycle
operations, telemetry observation semantics, and independent upgrade/rollback
procedures on **DGX Spark**.

## Web Console Overview

Spark Console binds strictly to `127.0.0.1:8877`. Access it from your
workstation over an SSH tunnel (`ssh -L 8877:127.0.0.1:8877 <user>@<spark-host>`):

<!-- ASSET_SLOT: docs/assets/screenshots/spark-console-overview.png | 16:9 redacted screenshot of Spark Console Overview / Devices pages (redact IMSI, hostnames, Tailnet IPs) -->

| Page | Route | Capabilities |
| --- | --- | --- |
| Overview | `/` | System health summary, telemetry freshness, RAN/core state, and active UE count |
| gNB | `/gnb` | OCUDU generation ID, USRP B210 state, RF baseline, and live `8879` scheduler telemetry |
| Core Network | `/core` | Open5GS 12-container health, N2 NG Setup readiness, and N3/N6/bridge counters |
| Devices | `/devices` | Evidence-correlated RNTI contexts and active PDU sessions (`/devices/{id}` detail view) |
| Events | `/events` | Filterable RAN, core, and collector event timeline |
| Metric history | `/history` | Retained SQLite time-series charts across configurable windows |
| Operations | `/operations` | Bounded stack/service control tasks, step logs, cancellation, and persistent audit trail |
| Diagnostics | `/diagnostics` | Subsystem probes, collector timestamps, and interface diagnostics |

Authenticated REST and SSE endpoints for custom dashboards and external AI
clients are specified in
[REST & SSE API Reference](reference/api-reference.md#spark-console-api-1270018877).

## Unified Full-Stack Lifecycle Control

For passwordless operator wrappers backed by `aoc-maintain`, copy the
lifecycle scripts (`deploy/spark/operations/{start.sh,stop.sh,platformctl.py}`)
into `~/aoc-ops/spark/` on Spark:

```sh
~/aoc-ops/spark/start.sh
~/aoc-ops/spark/stop.sh
/usr/bin/python3 -I ~/aoc-ops/spark/platformctl.py status
```

- **Startup order**: launches `core` (12 healthy Open5GS containers) -> `radio` (USRP B210 ready, `aoc-v2-cpu-latency.service`, and Open5GS N2 NG Setup complete) -> `monitor` (`aoc-control`, `aoc-observe`, `aoc-monitor-web`). Already-healthy stages remain running untouched.
- **Shutdown order**: stops `radio` -> `core` -> `monitor` so observability captures stack teardown cleanly while preserving the MongoDB database volume.
- **Pre-checks & serialization**: `start` validates listener ownership on port `8877` before applying mutations; issue lifecycle commands from a single control plane (`platformctl.py`, `aoc-v2ctl`, or Web Operations) at a time.

Timeouts, exit codes, and listener guard behavior are documented in
[Ports & Runtime Reference](reference/ports-and-runtime.md).

## Monitor-Only & Stack-Only Controls

- **Monitor-only maintenance**: Restart or inspect `aoc-observe.service`,
  `aoc-monitor-web.service`, and `aoc-control.service` independently without
  interrupting OCUDU or Open5GS. Verify readiness with:
  ```sh
  curl -fsS http://127.0.0.1:8877/api/v1/health
  ```
- **Direct stack control (`aoc-v2ctl`)**: Administrators may run `preflight`,
  `prepare`, `start`, `status`, and `stop` directly on the owned OCUDU/Open5GS
  stack. Persistent RF overrides reside in `deploy/spark/stack/runtime.py`;
  modify one RF parameter at a time and keep a clean backup prior to UE
  re-verification.
- **Streaming resilience**: Live SSE connections remain persistent across
  telemetry snapshots. If an executor stream closes mid-task, the API queries
  the in-flight task state rather than re-dispatching the mutation; inspect
  service status before retrying an interrupted operation.

## Upgrade and Rollback

Platform software upgrades independently while Open5GS and OCUDU stay online:

1. Stop only the three Spark Console services (`aoc-control`, `aoc-observe`, `aoc-monitor-web`).
2. Verify and install the target release (`install.py verify` -> `check-host` -> `install`, or via `aoc-maintain install`).
3. Start the three platform services and confirm `/api/v1/health` and live SSE telemetry resume.
4. If radio configuration or telemetry scripts (`enable_radio_json_metrics.py`) changed alongside a platform upgrade, restart `aoc-observe.service` after restarting the radio unit so the collector reattaches to the refreshed WebSocket stream.

To roll back, restore the matching pre-upgrade SQLite backup together with the
prior platform release without touching Open5GS or OCUDU.
