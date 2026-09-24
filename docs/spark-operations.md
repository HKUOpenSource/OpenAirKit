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
issued directly; all changes use the existing noninteractive `aoc-maintain` actions.
Unrelated containers and persistent data are retained.

Start requires all 12 core containers healthy, gNB active after its existing systemd
startup checks, and a healthy monitor/collector. These checks do not certify UE
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
Successful `status` queries return 0 even for a stopped stack. Output is English.

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
for the completed stop/start and repeat-call checks.

## Platform lifecycle

For monitor-only maintenance, the monitoring application uses `aoc-observe.service`,
`aoc-monitor-web.service` and `aoc-control.service`. Platform stop must leave
the radio and core services unchanged. Verify health at:

```sh
curl -fsS http://127.0.0.1:8877/api/v1/health
```

Use an SSH tunnel for browser access. Keep the listener on loopback.

## Observation

The platform reports host, B210, gNB, N2, core functions, interfaces, devices,
sessions and events. Source timestamps and evidence quality accompany values.
SSE loss marks live values stale or unknown. N3, N6 and bridge counters remain
separate, and a readable counter is not proof of recent traffic or an accepted
end-to-end path.

The Devices page correlates identities only when explicit evidence exists.
RNTI context and subscription session remain separate when correlation is
uncertain. The Operations page shows task steps, failures, cleanup and audit
history after a browser refresh.

## Stack lifecycle

Use `aoc-v2ctl preflight`, `prepare`, `start`, `status` and `stop` for the
owned OCUDU/Open5GS stack. Start requires core readiness, uncontested B210
ownership, a stable gNB process and N2. Stop records abnormal container or
service exits and retains owned resources when diagnosis is required.

Radio configuration changes must be one variable at a time, have a backup and
be followed by a same-condition UE benchmark and Spark evidence report.

## Upgrade and rollback

Platform releases can be upgraded while the protocol stack remains running.
Stop only the three platform units, verify/install the release, start them and
check health and SSE. Rollback must restore the previous release and database
backup without changing radio or core services.
