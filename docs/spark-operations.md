# Spark Platform Operations

[简体中文](spark-operations.zh-CN.md)

This guide covers daily Web Console usage, full-stack lifecycle management,
telemetry observation, and upgrade/rollback workflows on **DGX Spark**.

## Web Console Overview

Spark Platform listens on `127.0.0.1:8877`. Open it from your workstation via
an SSH tunnel (`ssh -L 8877:127.0.0.1:8877 <user>@<spark-host>`):

<!-- ASSET_SLOT: docs/assets/screenshots/spark-console-overview.png | 16:9 redacted screenshot of Spark Platform Overview / Devices pages (redact IMSI, hostnames, Tailnet IPs) -->

| Page | Route | Capabilities |
| --- | --- | --- |
| Overview | `/` | System health summary, evidence freshness, RAN/core state, and active UE count |
| gNB | `/gnb` | OCUDU generation, USRP B210 state, RF baseline, and live `8879` scheduler telemetry |
| Core Network | `/core` | Open5GS 12-container status, N2 NG Setup readiness, and N3/N6/bridge counters |
| Devices | `/devices` | Evidence-correlated RNTI contexts and active PDU sessions (`/devices/{id}` detail view) |
| Events | `/events` | Filterable RAN, core, and collector event timeline |
| Metric history | `/history` | Retained time-series charts across configurable windows |
| Operations | `/operations` | Bounded stack/service control tasks, step logs, cancellation, and audit trail |
| Diagnostics | `/diagnostics` | Subsystem probes, collector timestamps, and interface diagnostics |

Authenticated REST and SSE endpoints for custom dashboards or DIY AI modules
are documented in [REST & SSE API Reference](reference/api-reference.md#spark-platform-api-1270018877).

## Full-Stack Lifecycle

For operator shortcuts using `aoc-maintain`, copy the standalone lifecycle
scripts (`deploy/spark/operations/{start.sh,stop.sh,platformctl.py}`) into
`~/aoc-ops/spark/` on Spark:

```sh
~/aoc-ops/spark/start.sh
~/aoc-ops/spark/stop.sh
/usr/bin/python3 -I ~/aoc-ops/spark/platformctl.py status
```

- **Startup sequence**: starts `core` (12 healthy Open5GS containers) -> `radio` (USRP B210 ready, `aoc-v2-cpu-latency.service`, and Open5GS N2 NG Setup succeeded) -> `monitor` (`aoc-control`, `aoc-observe`, `aoc-monitor-web`). Already-healthy stages are preserved.
- **Shutdown sequence**: stops `radio` -> `core` -> `monitor` so observability stays live throughout stack teardown while preserving the MongoDB database volume.
- **Preflight & concurrency**: `start` checks port `8877` listener ownership before applying changes; run lifecycle commands from one entrypoint at a time (`platformctl.py`, `aoc-v2ctl`, or Web Operations).

Timeouts, exit codes, and listener guard details live in
[Ports & Runtime Reference](reference/ports-and-runtime.md).

## Monitor-Only & Stack-Only Controls

- **Monitor-only maintenance**: Restart or inspect `aoc-observe.service`,
  `aoc-monitor-web.service`, and `aoc-control.service` independently without
  affecting OCUDU or Open5GS. Verify readiness with:
  ```sh
  curl -fsS http://127.0.0.1:8877/api/v1/health
  ```
- **Direct stack control (`aoc-v2ctl`)**: Administrators can run `preflight`,
  `prepare`, `start`, `status`, and `stop` directly on the owned OCUDU/Open5GS
  stack. Persistent RF overrides live in `deploy/spark/stack/runtime.py`;
  change one RF variable at a time and keep a backup before re-testing with a
  connected UE.
- **Telemetry behavior**: Live SSE streams remain persistent across snapshots.
  If an executor stream closes mid-task, the API queries the existing task state
  directly instead of re-sending the mutation; check service status before
  retrying interrupted actions.

## Upgrade and Rollback

Platform releases upgrade independently while Open5GS and OCUDU keep running:

1. Stop only the three Spark Platform services (`aoc-control`, `aoc-observe`, `aoc-monitor-web`).
2. Verify and install the target release (`install.py verify` -> `check-host` -> `install`, or via `aoc-maintain install`).
3. Start the three platform services and verify `/api/v1/health` and live SSE updates.
4. If radio configuration or telemetry scripts (`enable_radio_json_metrics.py`) were updated alongside a platform upgrade, restart `aoc-observe.service` after restarting the radio service so the collector attaches to the refreshed telemetry socket.

To roll back, restore the matching pre-upgrade database backup alongside the
previous platform release without touching Open5GS or OCUDU.
