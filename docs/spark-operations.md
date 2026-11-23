# Spark Platform operations

## One-command full-stack lifecycle

Run locally as the commissioned SSH user:

```sh
~/aoc-ops/spark/start.sh
~/aoc-ops/spark/stop.sh
/usr/bin/python3 -I ~/aoc-ops/spark/platformctl.py status
```

These shortcuts control Open5GS, OCUDU gNB and all three monitor services. Start
orders core, radio, then monitor; stop orders radio, core, then monitor so observation
remains available during shutdown. Only the fixed `aoc-v2-*` stack units and the
`aoc-v2-open5gs` project's 12 expected services are checked. No Docker mutation is
issued directly; all changes use the existing noninteractive `aoc-maintain` actions
(`status`, `verify`, `install`, `rollback`, `start`, `stop`, `radio-*`, `core-*`,
`connectivity-upgrade`). Unrelated containers and persistent data are retained.

Before changing services, start checks both IPv4 and IPv6 listeners on port 8877
using `ss --cgroup`. An occupied port is accepted only when every listener belongs
to the running Web unit's systemd control group and its health endpoint responds
OK. Foreign or unverifiable ownership, inspection failure, or an unhealthy existing
Web service stops startup before any changes. This requires kernel/iproute2 cgroup
reporting and does not reserve the port against a later concurrent administrator action.

Start requires all 12 core containers healthy, gNB active after its existing systemd
startup checks, a successful N2 NG Setup from the Open5GS infoAPI, and a healthy
monitor/collector. A running gNB alone is not sufficient. These checks do not certify UE
attachment. Already-running components are checked without restart; missing stages
are started in dependency order. An active unhealthy core or partially running core
containers cause an error rather than an implicit restart. A startup failure preserves
completed stages. A stop failure halts before stopping dependencies or the monitor;
remaining containers or processes cannot be reported as successfully stopped.

Helper calls have a 330-second timeout and each health wait has a 60-second budget.
No write is automatically retried or rolled back. On timeout or interruption, query
status first: a systemd job may still be running. A user-level lock prevents overlapping
script runs, including copies, but does not serialize all UI/administrator paths;
do not mix those entrypoints during an operation. The helper retains its own checks.
Exit codes: 0 success, 1 execution/verification failure, 2 invalid arguments, 3 busy.
Successful `status` queries return 0 even for a stopped stack. Status distinguishes
core health, radio process state and verified N2 setup; UE connectivity requires
separate device evidence. Output is English.

The standalone scripts require system Python, systemd tools, `ss`, Docker read access
and the existing restricted maintenance permission. After backing up an existing
destination, install from a checkout or transfer the same files over SSH:

```sh
mkdir -p ~/aoc-ops/spark
install -m 0755 deploy/spark/operations/start.sh deploy/spark/operations/stop.sh \
  deploy/spark/operations/platformctl.py ~/aoc-ops/spark/
```

Verify transfer hashes before execution. No repository or virtual environment is
needed on the device. Scripts are delivered separately from the application release;
restoring their backup does not roll back the application. They do not enable boot
startup or contain device connection addresses.
See the [2026-09-24 lifecycle acceptance](acceptance/2026-09-24-platform-lifecycle.md)
and [2026-11-23 alignment record](acceptance/2026-11-23-spark-ue-alignment.md)
for completed checks.

## Platform lifecycle

For monitor-only maintenance, the monitoring application uses `aoc-observe.service`,
`aoc-monitor-web.service` and `aoc-control.service`. Platform stop must leave
the radio and core services unchanged. Verify health at:

```sh
curl -fsS http://127.0.0.1:8877/api/v1/health
```

Use an SSH tunnel for browser access. Keep the listener on loopback.

## Observation, telemetry and bridge counters

The platform reports host, B210, gNB, N2, core functions, interfaces, devices,
sessions and events. Source timestamps and evidence quality accompany values.
SSE loss marks live values stale or unknown. N3, N6 and bridge counters remain
separate, and a readable counter is not proof of recent traffic or an accepted
end-to-end path.

- **OCUDU JSON metrics (`127.0.0.1:8879`)**: `aoc-observe.service` connects over
  WebSocket to `ws://127.0.0.1:8879` (moved from `8001` to avoid co-located vLLM
  containers). `aoc-v2-metrics-guard.service` (`RemainAfterExit=yes`) installs
  `table inet aoc_v2_metrics_guard` blocking non-root clients on `8879`. When
  rolling back or migrating the metrics transaction with
  `scripts/spark/enable_radio_json_metrics.py`, `remove_guard()` explicitly stops
  `aoc-v2-metrics-guard.service` before deleting the nftables table so systemd
  re-runs the guard on subsequent radio starts.
- **Dynamic Docker bridge resolution**: `collector.py::bridge_interface()` reads
  the owned `aoc-v2-open5gs-core` bridge name dynamically from Docker rather than
  assuming a static interface name, handling auto-generated `br-<id12>` names.

Healthy SSE connections remain open, with session checks before every published
snapshot. The web process retains a 10-second graceful-shutdown limit; routine
15-second connection rotation is not expected. A recurring loss banner should be
checked against service restarts, tunnel health and collector timestamps.

The Devices page correlates identities only when explicit evidence exists.
RNTI context and subscription session remain separate when correlation is
uncertain. The Operations page shows task steps, failures, cleanup and audit
history after a browser refresh.
If the executor stream closes before a terminal result, the API queries the same
task instead of resending the operation. An unknown task or unavailable executor
is recorded as interrupted, releasing the API's task reservation; inspect service
state before requesting another operation because the original action may have run.

## Stack lifecycle

Use `aoc-v2ctl preflight`, `prepare`, `start`, `status` and `stop` for the
owned OCUDU/Open5GS stack. Start requires core readiness, uncontested B210
ownership, a stable gNB process, `aoc-v2-cpu-latency.service` (`PartOf=aoc-v2-radio.service`),
and N2. Stop records abnormal container or service exits and retains owned resources
when diagnosis is required. Keep persistent RF parameters (`rx_gain=54`,
`pusch.max_ue_mcs=24`) in `runtime.py` rather than ephemeral `/run/systemd/system/`
drop-ins, and retain `realtime.conf` (`CPUAffinity`, `LimitRTPRIO=99`) where
workload isolation is required.

Radio configuration changes must be one variable at a time, have a backup and
be followed by a same-condition UE benchmark and Spark evidence report.

## Upgrade and rollback

Platform releases can be upgraded while the protocol stack remains running.
Stop only the three platform units, verify/install the release, start them and
check health and SSE. Rollback must restore the previous release and database
backup without changing radio or core services. If upgrading `runtime.py` or
`enable_radio_json_metrics.py`, restart `aoc-observe.service` after restarting
the radio so `SchedulerFeed` binds to the updated `127.0.0.1:8879` socket.

Database schema 6 indexes retained metric names for history menus. The installer
backs up and migrates existing data before web startup. Allow time for the one-time
backfill; subsequent menu reads use the index. Downgrading requires the matching
database backup, since earlier code cannot open schema 6.
