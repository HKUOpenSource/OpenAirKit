# UI deployment and hardware checks — 2026-09-27

[简体中文](2026-09-27-ui-deployment.zh-CN.md)

Source: working tree based on `87e059fd5b4010384606eca6180bd0f3ecc86aa1`.
The user authorized deployment to one Spark and two Jetsons and activated the
approved bundles. The new UI releases are installed and serving traffic on all
three devices. Further Spark history performance and periodic live-stream closure
corrections found during hardware acceptance were deployed on 2026-09-28. This record
supplements the [UI fixes](2026-09-27-ui-fixes.md).

## Deployment correction

There is no CodeGraph index. The question was whether a Jetson rollback restores
the service definition as well as the application and database. The call path is
maintenance install → `manage.install` → `backup`, and maintenance rollback →
`manage.rollback` → systemd web start. Previously the new service definitions
could survive a rollback. Checkpoints now save the installed unit contents;
rollback restores them and runs `daemon-reload` before web startup. Older
checkpoints use the saved release's packaged units. The device service still
requires explicit startup after inspection.

The regression test changes installed unit contents after creating a checkpoint
and verifies exact restoration and reload-before-start ordering, alongside the
existing configuration and database restoration checks. Live application rollback
has not been exercised in this run.

## Artifacts and native validation

| Target | Application release | Approved bundle SHA-256 | Native isolated tests |
| --- | --- | --- | --- |
| Jetson A and B, ARM64 / Python 3.10 | Console 0.6.0, `9ed9fbcf1d68bf78` | `7508b2ea1f9e4faf23df16b4e5ca04b38c0964c5ea05155cece60ffee7109875` | 30 passed on each device |
| Spark, ARM64 / Python 3.12 | Platform 0.2.0, `a4f6b8caf8f015af` | `601b5eb7b4f3c77c1fde94130cc77442d1c5d9cdd1b81c20231c02ad009f540d` | 23 original and six follow-up tests passed |

All targets passed archive checksums, maintenance bootstrap `--check` and native
`visudo` validation. Offline dependencies installed into private test environments
from the locked wheel bundles. Jetson tests cover agent and modem behavior with
simulation/mocks; Spark tests cover connection health, Open5GS parsing and
telemetry. They do not certify new application behavior against live radio data.
Final remote verification matched all 51 Jetson and 28 Spark manifest entries;
activation script syntax passed. Existing web health was `ok` on all targets,
Spark collector health was `ok`, and all managed services remained active.

Local validation: 293 Python tests passed with one existing macOS skip; seven
frontend behavior tests passed. TypeScript, documentation, release-boundary,
license and shell checks passed. The stack suite initially hit the local sandbox
loopback restriction; rerunning with the required permission passed all 156 tests.
The Jetson suite passed all 79 tests again after the rollback correction.
Astryx and device-local state boundaries are preserved.

## Hardware observations and completed deployment

- Both Jetsons upgraded sequentially from `8ade791a3317ad5e` to `9ed9fbcf1d68bf78`.
  After explicit start, both were registered, had active data sessions and
  protected management connectivity, with recovery paused.
- Spark upgraded from `5bc68497243efdf5` to `5da6e62f02a72823`. Core and radio PIDs
  and activation timestamps were unchanged across installation. All twelve core
  containers, N2 and the three monitor services passed health checks.
- Updated Spark's user-owned `aoc-ops/spark/platformctl.py`, keeping a sibling
  `platformctl.py.before-ui-20260927` backup. Installed SHA-256:
  `03aed6627e04315a1e821f38e9429ebb7b4ac12a75cd1455d37ecb18c4afe535`.
  Running its normal `start.sh` succeeded with healthy stack, N2 and monitor
  checks. All five service PIDs and activation timestamps stayed unchanged.

## Live application acceptance

All installed manifest files matched approved content and root ownership (51 per
Jetson, 28 on Spark). HTTP index and JS/CSS hashes matched the packages (six routes
per Jetson, four on Spark). Health passed and protected APIs rejected anonymous
requests with HTTP 401. The first broad static-file probe included packaged
license notices, which are not public asset routes; validation was corrected to
check the actual index and asset routes.

After the user signed in, in-app Browser checks confirmed both Jetsons' live
connection evidence, Setup assessments and observation-only labels, safe
confirmation dismissal with focus restoration, updating history samples and the
30-day event / 7-day metric limit. Spark showed two active data sessions, useful
empty-filter feedback, priority gNB summaries and expandable details, retained
history sources, stable event categories after filtering and operation history.
No live recovery, modem reconfiguration or radio stop was triggered. Mobile checks
remain the earlier simulator evidence; live rollback was not rehearsed.

## Spark follow-up corrections deployed on 2026-09-28

Hardware acceptance exposed a slow first load of Spark's history catalog. The
call path `HistoryPage` → `history/catalog` → `Store.history_catalog` scanned all
retained sample JSON for every entity. Schema 6 adds a compact metric-name index,
backfills it once from retained samples and updates it during ingestion. Index
entries expire with metric retention, preserving old names and offline entities.
The installer backs up the database and completes migration before starting the
bounded service-health wait; its existing recovery path restores the database if
installation fails.

Two new tests cover v5 migration, backup, no sample-table reads during catalog
requests, out-of-order ingestion and retention. Spark tests after the combined
correction: 64 passed, one
existing macOS skip; stack tests: 156 passed. Both new tests passed natively on
Spark. A synthetic ARM64 benchmark with 30,000 samples, 30 entities and 12 metrics
per entity produced identical catalogs: the old scan took 0.267 seconds, one-time
migration 0.651 seconds, and indexed reads 0.00044–0.00101 seconds. These are
synthetic timings, not measurements of the production database.

The user also reported frequent `Live connection lost` banners. The
`/api/v1/stream` generator explicitly closed every 15 seconds, triggering the
frontend EventSource error handler despite healthy services. Web and observation
services had zero restarts, and sanitized journal checks found no database-lock
errors or tracebacks. Streams now continue until client disconnect, session
expiry or shutdown. Session validity is checked both before and after snapshot
reads. The existing 10-second Uvicorn graceful-shutdown bound remains within the
15-second systemd stop timeout; genuine transport failures still surface in the UI.
Four regression tests cover 50 seconds of simulated stream lifetime, logout,
expiry during snapshot reads, and shutdown cancellation.
All six follow-up regressions passed natively on Spark. An isolated real HTTP
probe reproduced the old stream ending after 16.032 seconds. With the correction,
one authenticated connection remained open for 40.069 seconds and service shutdown
with that stream still open completed in 10.137 seconds. The probe used temporary
synthetic authentication and data, not production credentials or control actions.

Combined release `a4f6b8caf8f015af` was verified and uploaded to Spark's private
`~/aoc-ui-spark-final-20260927` directory, superseding the history-only candidate.
Approved-bundle SHA-256:
`601b5eb7b4f3c77c1fde94130cc77442d1c5d9cdd1b81c20231c02ad009f540d`.
Native bootstrap checks and archive verification passed. After administrator
activation, the approved helper installed the release and migrated the existing
history database. Final installed ownership/checksums matched all 28 manifest
entries; all four HTTP index/asset routes matched the package. Web and collector
health were `ok`, both services had zero automatic restarts, and core/radio PIDs
and activation timestamps were unchanged. Both Jetsons still reported registered,
active data sessions and protected management access.

With the user signed in, a full browser reload populated the real history component
selector in 282 ms, including navigation and browser automation overhead. The
metric selector was enabled and the Host CPU chart showed current samples. This
is an observed UI readiness time, not an isolated API latency measurement.

The authenticated production page was sampled 45 times over 45.707 seconds:
every check displayed `Live data`, with zero `Live connection lost` banners.
Chart sample timestamps advanced. Independently, loopback TCP counters confirmed
two identical socket identities continued sending data for 44.39 seconds without
new client request bytes, crossing the former 15-second stream lifetime. The
temporary acceptance tab was closed and the user's Spark console left available.
This completes the targeted deployment acceptance; it is a bounded observation,
not a guarantee against future network outages. No live rollback was performed.
