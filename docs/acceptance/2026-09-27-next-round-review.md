# Next development review — 2026-09-27

[简体中文](2026-09-27-next-round-review.zh-CN.md)

Follow-up: the three P1 items below have subsequent
[source fixes and regression evidence](2026-09-27-p1-reliability-fixes.md).
Subsequent [deployment evidence](2026-09-27-ui-deployment.md) records their rollout;
this review retains the original baseline.

Reviewed revision: `87e059fd5b4010384606eca6180bd0f3ecc86aa1`, initially clean
`main`. The current three-device system is running OCUDU. Local builds and tests
pass, but the failure paths below should be addressed before extending hardware
acceptance. This record does not close any [roadmap](../roadmap.md) gate.

## Scope and evidence

Question: what is the current source/device baseline, which defects remain after
the lifecycle merge, and what should the next development round address?
There is no `.codegraph/` index, so direct source inspection was used. Review
covered both applications, lifecycle and release tools, subscription maintenance,
tests and the chronological acceptance records. Findings below use isolated
synthetic reproductions or explicitly identified static analysis.

SSH observations were taken at approximately 19:53 Hong Kong time on September 27.
They read selected systemd properties, public loopback health, project-scoped
container status, N2 information, installed file hashes and USB product IDs.
Each Jetson's existing restricted `ue-status` action returned a filtered status
snapshot; it uses the maintenance helper's normal lock. No service switch,
deployment, modem write, route change, new data probe or fault injection ran.
Addresses, credentials, subscriber identities and raw operational logs are omitted.

## Current device baseline

Jetson A denotes the first supplied Jetson; Jetson B denotes the second.

| Evidence | Spark | Jetson A | Jetson B |
| --- | --- | --- | --- |
| SSH / architecture | Reachable / ARM64 | Reachable / ARM64 | Reachable / ARM64 |
| Python | 3.12.3 | 3.10.12 | 3.10.12 |
| Installed application | 0.2.0 | 0.6.0 | 0.6.0 |
| Release ID | `5bc68497243efdf5` | `8ade791a3317ad5e` | `8ade791a3317ad5e` |
| Manifest-listed files matching | 28/28 | 51/51 | 51/51 |
| Project services | Core active/exited; radio and all three monitor services active/running | Device and Web active/running | Device and Web active/running |
| Automatic restart counters | All zero | Both zero | Both zero |
| Public application health | OK, collector OK | OK, Web OK | OK, Web OK |
| USB product | B210 | Quectel modem | Quectel modem |
| Current UE evidence | Not independently re-correlated in this review | Quality OK; registered; PDU active; connected | Quality OK; registered; PDU active; connected |
| Observation / automatic recovery | — | Enabled / paused | Enabled / paused |

All 12 project core containers were running and healthy. The current N2 response
contained one gNB with successful setup. Both UE snapshots were approximately
13–15 seconds old at collection. They report verified connectivity; this review
did not repeat the independent interface-bound probes from the
[deployment acceptance](2026-09-27-independent-lifecycle-deployment.md).

Both Jetsons report protected management, with Wi-Fi as their only main-table
IPv4 default interface. This does not independently establish the actual tunnel
transport or its policy-routing path. The unprivileged SSH users could not inspect
the protected device-socket directory; the authorized status RPC succeeded.

The other platform's inspected services are inactive. Some remain enabled at boot,
while project monitor and Jetson services are disabled and project core/radio units
are static. A reboot is therefore not a validated way to restore this running
OCUDU baseline; choose and verify resource ownership before reboot acceptance.

Release manifest SHA-256:

- Spark: `d37822fdad93c2c5fe842411b32b2de348fefd7d218d3e8f4e01afcf83634a9e`.
- Both Jetsons: `e297880d5a4ac2ec4f04395efbf76e113d7e61c62a977c62a8f0edee1340ae40`.

The installed Spark and Jetson lifecycle controllers match current source hashes:
`b2867227b14f3678824cdb214bcea6c858c0430beaf7c4d028c4775db785549a`
and `eed4dced9dbf8f9a87c827c4d8f48ee7fc804b49a9b6fd9b4ee027f20c72b453`,
respectively. Application manifests still say `dirty=true`, with Spark based on
`fd3b3b0` and Jetson on `39dde4d`. Matching listed files establishes their integrity,
not complete equivalence to clean current HEAD. Build the next release from a
clean revision and retain its provenance.

## Confirmed code findings

### P1 — A failed CFUN readback can leave the modem switched off

The path is `Agent.execute → Agent.write(cfun0) → Modem.write → exchange →
query(AT+CFUN?)`, at [agent.py](../../apps/jetson-console/backend/aoc_jetson/agent.py)
lines 383 and 412 and [modem.py](../../apps/jetson-console/backend/aoc_jetson/modem.py)
lines 224–230. If CFUN=0 takes effect but its response/readback fails, execution
skips CFUN=1. Failure cleanup only restores network routing, and power-restoration
authorization is set only after successful readback. An isolated recovery task
ended failed with functionality 0, only `cfun0` in its write history, and recovery
paused. Hardware occurrence has not been measured.

Add bounded power-restoration handling for an uncertain write result. Test a lost
acknowledgement, failed readback, cancellation and failed CFUN=1; preserve modem
ownership and independent management protection throughout.

### P1 — Spark control EOF leaves an unfinished task blocking later operations

The path is `POST /control → run_control → control_messages → reader.readline`,
at [web.py](../../apps/spark-platform/backend/aoc_spark/web.py) lines 83–85 and
118–130. EOF after a `running` response ends iteration normally, bypassing the
exception handler that calls `poll_control`. The persisted task stays running,
and the next operation is rejected by
[storage.py](../../apps/spark-platform/backend/aoc_spark/storage.py) line 132.
An isolated `running → EOF` reproduction returned `operation_in_progress` on
the next task. Web startup reconciliation can recover it; the live process does
not reconcile this normal EOF path.

Recover or terminate every unfinished stream on EOF. Test EOF before the first
message, after running, and after a terminal result without duplicating operations.

### P1 — Spark startup mutates the stack before rejecting a foreign Web listener

The path is `start.sh → Controller.start → core-start → radio-start → start`,
at [platformctl.py](../../deploy/spark/operations/platformctl.py) lines 225–250.
With the project stopped and another listener on its Web port, startup can start
core/radio before Web readiness fails. A mock with `listening=True` recorded all
three mutations and zero listener checks. The added N2 gate did not fix this
earlier readiness finding. The current live listener is not reported as a conflict.

Check port/resource ownership before mutations and cover foreign IPv4/IPv6
listeners, zero-change rejection and idempotent startup of the owned healthy
service. Review the equivalent Jetson boundary when implementing this guard.

### P2 — Spark diagnostic redaction misses observation values

The path is `Collector.host → snapshot → diagnostics → redacted_diagnostics`,
at [web.py](../../apps/spark-platform/backend/aoc_spark/web.py) lines 25–43.
The filter compares dictionary keys, but an observation stores a sensitive field
as `name=b210_serial` and its content under `value`. Synthetic serial/PID values
survived export; `details.InvocationID` also bypasses `invocation_id` matching.
This is an export defect, not evidence that credentials were exposed in this review.

Use observation-aware redaction and normalized field names. Test top-level
observations, nested component metrics and systemd details with synthetic data.

### P2 — One idle UE hides aggregate radio throughput

The path is `SchedulerFeed.receive → parse_ocudu → Collector.collect → UI`,
at [telemetry.py](../../apps/spark-platform/backend/aoc_spark/telemetry.py)
lines 52–77. A UE with explicitly zero transport blocks gets a null bitrate;
aggregation requires every UE value to be non-null. A synthetic active UE at
23 Mbps downlink / 5 Mbps uplink plus an idle UE produced unavailable totals.
The synthetic idle UE explicitly reported zero bitrate and zero OK/NOK
transport-block counters in both directions.

Distinguish explicit zero traffic from missing telemetry; zero block counts alone
must not replace a missing bitrate with zero. Test both idle, one
active, both active and genuinely missing fields; retain unavailable BLER/MCS
semantics when no blocks exist.

### P2 — Active-device views count inactive or unknown PDU state

The path is `Open5GS.parse_info → fresh_snapshot → Overview/Devices filters`,
at [OverviewPage.tsx](../../apps/spark-platform/frontend/src/pages/OverviewPage.tsx)
lines 98–104 and [DevicesPage.tsx](../../apps/spark-platform/frontend/src/pages/DevicesPage.tsx)
lines 78–84. Both filters require session evidence quality `status=ok` but ignore
`session.state`. Synthetic inactive/unknown sessions yielded backend
`active_pdu_count=0` while satisfying the UI's Active predicate.

Share a definition that also checks active session state and freshness. Test
active, inactive, unknown and expired evidence without conflating active PDU with
verified end-to-end connectivity.

### P2 — A paused or merely created Jetson job stops background observation

The path is `create → current → manual execute → paused → serve`, at
[agent.py](../../apps/jetson-console/backend/aoc_jetson/agent.py) lines 607–609.
Only terminal jobs clear `current`; background sampling requires no current job.
A manual job paused after its first step prevented new samples and its synthetic
status became stale/disconnected after 21 seconds. SSE continues sending cached
state. A ready job that has not started has the same scheduling condition.

Separate reserved task ownership from active modem execution. Test continued
read-only observation while ready/paused, without concurrent serial access or
automatic recovery during manual work.

## Release and acceptance gaps

- **Conditional rollback risk:** installation overwrites systemd units, but
  [manage.py](../../deploy/jetson/manage.py) rollback lines 371–374 only switches
  the release and starts Web. A future unit change can leave old code with new
  units. Current historical units are unchanged, so this is not a demonstrated
  existing-version rollback failure. Test two different unit versions and restore
  units with daemon-reload as part of rollback.
- **Subscription recovery evidence:** `sync-subscriptions.apply` performs backup,
  temporary Mongo startup, sequential inserts, readback and cleanup. Existing
  tests cover helper behavior rather than the whole failure sequence. Add partial
  insertion, lost acknowledgement, disk-full and cleanup failure cases on synthetic
  data, followed by backup restoration to a separate volume. The earlier real
  import did not certify database restoration. No new defect was established in
  insert-only decisions or BSON Int64 SQN preservation.
- **Management prerequisite:** `inspect_management` now requires a preferred Wi-Fi
  IPv4 default as well as an overlay route, but does not verify the actual tunnel
  transport with its routing mark. Verify that independent path before disruptive
  modem/failure tests; this read-only review did not establish it.

## Development order

First address the three P1 failure paths with isolated regression tests. Next
correct export redaction, dual-UE telemetry/state semantics and paused-job
observation. Before release, cover changed-unit rollback, build clean ARM64
artifacts and exercise the manual Python/browser matrix. Then validate both
Jetsons against P3-15, P3-16, P3-17 and R06: fault matrix, install/rollback/reinstall,
management preservation and exactly five stop/start/reconnection cycles with one
modem controller. Evaluate P3-GATE only after those records exist. Subscription
restore testing precedes further subscription-maintenance expansion.

Keep [the roadmap](../roadmap.md) as the only completion checklist. The later
activation in the deployment record supersedes older same-day stopped-state
snapshots; historical acceptance records remain unchanged.

## Validation and limitations

`make ci VENV=local/bootstrap-check` passed: Jetson 72 tests, Spark 53 including
one existing macOS peer-credential skip, shared stack 150. Total: **274 passed,
one skipped**. Both locked frontend installs, production builds, TypeScript checks,
documentation, release-boundary, license and shell audits passed. Both frontend
builds retain the existing warning for chunks above 500 kB.

An earlier sandboxed `make check` was interrupted by a shared HTTP test being
unable to bind localhost. That target and the complete `make ci` passed with
loopback permission; tests were not changed. Local versions are Python 3.11.15
and Node 24.14.0, not the CI Python 3.12 / Node 22 pair. The default `.venv` is
Python 3.9.6 and is unsuitable; use the existing `local/bootstrap-check` environment
for local checks or bootstrap a fresh supported environment. Target Python
3.10/3.12 matrix and browser E2E were not executed in this review.

Only this paired report, documentation navigation and current roadmap prose were
changed. No application fix, deployment, hardware rollback or gate completion is
claimed. Follow-up documentation audit and whitespace checks apply to these edits.
