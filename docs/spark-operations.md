# Spark Platform operations

## Platform lifecycle

The monitoring application uses `aoc-observe.service`,
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
