# Local platform lifecycle scripts — 2026-09-24

[简体中文](2026-09-24-platform-lifecycle.zh-CN.md)

Source base: `dba599c830f2abe6a09309ca85a52afd281519cf`, with uncommitted lifecycle
implementation and documentation changes. Applications remain Spark 0.2.0 and Jetson
0.5.1. The standalone scripts were deployed to each device's `~/aoc-ops/<platform>/`
directory and exercised on native ARM64 Python 3.12.3 / 3.10.12 respectively.

## Question, call path and impact

Question: can operators start/stop each platform locally with one command, including
the Spark radio and core, while retaining existing privileged boundaries? No
`.codegraph/` index exists; current deployment and maintenance paths were inspected
directly. The path is `start.sh / stop.sh → platformctl.py → sudo -n aoc-maintain →
approved manager / systemd`. Observations use fixed unit names, loopback health,
project-scoped local Docker reads, and the existing restricted UE-status action.

Spark starts core → gNB → monitor, and stops gNB → core → monitor. Jetson operates
only its two V2 services. Failures preserve state; repeated calls do not restart
healthy services. The scripts never request a modem recovery, arbitrary command,
Docker mutation, new maintenance permission or boot enablement. Jetson lifecycle
files are excluded from application release staging; Spark operations were already
outside its explicit application staging inputs.

See the [Spark](../spark-operations.md) and [Jetson](../jetson-operations.md)
operations guides for installation, timeouts, exit codes and concurrency limits.

## Validation

- Added 32 isolated lifecycle tests for order, idempotence, partial/unhealthy state,
  retained failure state, residual processes/containers/socket/listener, permissions,
  timeouts, operation locking, wrapper paths, fixed helper actions and Docker scope.
- `make ci VENV=local/bootstrap-check` passed before the final socket-visibility
  correction: both production frontend builds, 242 passing tests, one existing
  macOS peer-credential skip, and repository audits.
- Final `make check VENV=local/bootstrap-check` passed after that correction:
  Jetson 58 passed; Spark 52 passed and one skip; root stack/release/lifecycle 134
  passed. Total: 244 passed, one skip. TypeScript, documentation, release-boundary,
  license and Shell checks passed. `git diff --check` passed.
- Local checks used Python 3.11.15 and Node 24.14.0; this does not replace the
  release matrix on Python 3.10/3.12 and Node 22. The standalone scripts themselves
  were executed on both target interpreters. Existing frontend bundle-size warnings
  remain; this change does not modify the frontend.

The first Jetson status check exposed a protected `0750` runtime directory: a
non-root `Path.exists()` raised PermissionError while all services were healthy.
The corrected script reads kernel socket visibility when necessary, reports
inaccessible evidence explicitly, and never treats a permission error as absence.
Two regressions cover this case. No permission or group membership was changed.

## Hardware acceptance

Both initial destination directories were absent. Transfers were SHA-256 verified;
the intermediate Jetson script was backed up before its socket correction. Script
rollback was not exercised; removing a first installation or restoring reviewed
script copies affects only operator tooling, not the installed application release.

All of the following commands ran from `/tmp`, verifying working-directory
independence; the eight start/stop invocations returned zero:

1. Jetson `stop.sh`, then `stop.sh` again: both V2 services inactive, PIDs zero,
   device socket absent and port 8878 not listening. The repeated call issued no
   additional stop action.
2. Spark `stop.sh`, then `stop.sh` again: gNB, core and three monitor units inactive,
   PIDs zero, no project core containers remaining and port 8877 not listening.
   Container removal is the existing core-stop behavior; the script does not issue
   removal or volume commands. The repeated call issued no additional stop action.
3. Spark `start.sh`, then `start.sh` again: 12 expected core containers healthy,
   radio active after existing startup checks, all monitor units active, health and
   collector `ok`. Repeated start kept the same radio/monitor PIDs and issued no
   start action.
4. Jetson `start.sh`, then `start.sh` again: both V2 services active, web available,
   repeated start retained PIDs and issued no start action. Initial cached evidence
   was stale and correctly produced a warning. Final executor evidence was fresh:
   registered, data session active, lab policy matched and RNDIS-bound connection
   verified. Maintenance remained off and recovery paused, matching the baseline.

No explicit modem reconnect/recovery was invoked. This records one complete
stop/start cycle, not the roadmap's five-cycle or full fault-matrix acceptance.
Live failure injection, authenticated browser inspection and independent correlated
RAN/UE end-to-end acceptance are outside this run. The known management-path
protection finding is unchanged; `management_protected=true` does not resolve it.

Final comparisons confirmed:

- Spark release `5bc68497243efdf5`, Jetson release `186b6c4659cc5e14`, both release
  links and manifest hashes unchanged; all 28 Spark and 48 Jetson files match.
- Installed maintenance-helper hashes and all inspected unit boot policies unchanged;
  application services disabled at boot, radio/core static. No automatic restarts.
- All 47 unrelated Spark containers retain their identity, state, start time and
  restart count. No raw container inventory or operational logs are committed.

## Delivered script SHA-256

| File | SHA-256 |
| --- | --- |
| Both platforms: `start.sh` | `2ef85b63c47b0c7d05b35775ae56c2be159ba8d95e72ea3f14329e2b0abe6c77` |
| Both platforms: `stop.sh` | `2fda486b618c627756119499d2f9ecefbf0a6ec0ac6b4780c3cbfd10fcdda583` |
| Spark: `platformctl.py` | `dca4cd6167ecd157758c069c86932ebcf92d75ed3a3a0008fc8453cddd1e5f9f` |
| Jetson: `platformctl.py` | `c0a9b6634a1e8271bb86d3591e304df7c57e9558437bc81a6dd8ef276d5d1bdc` |

The roadmap remains the only completion checklist; no Gate was changed.
