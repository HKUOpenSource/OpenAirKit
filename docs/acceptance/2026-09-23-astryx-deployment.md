# Astryx device deployment — 2026-09-23

[简体中文](2026-09-23-astryx-deployment.zh-CN.md)

This records the initial Astryx rollout. Jetson was subsequently upgraded to
[0.5.1 for the live update repair](2026-09-23-jetson-live-stream.md).

Status: deployed to both devices after administrator activation of the exact
maintenance approvals. Each platform passed installation, rollback to its previous
release and reinstallation. The releases below were healthy at this deployment.
No radio/core restart or modem recovery/reset action was requested.

| Platform | Version | Release at this deployment | Previous release |
| --- | --- | --- | --- |
| Spark | 0.2.0 | `5bc68497243efdf5` | `d987aca4396311d2` |
| Jetson | 0.5.0 | `c4e60f990fc61882` | `0826938fd08ae477` |

Source is the current working tree (manifest records `dirty=true`), including the
Astryx migration, Spark numeric Identity projection and Jetson P2 passive-rate
fix. Versions are synchronized in backend, frontend/lock files, staging code and
changelog. Artifacts are development candidates, not clean-source releases.

## Checks and staging

- `make check VENV=local/bootstrap-check`: 207 passed, one platform-dependent
  skip; both TypeScript checks and documentation/release/license/shell audits pass.
- Both official ARM64 offline archive builders pass; target wheel tags, lock
  membership and transitive dependencies are validated.
- Both devices validate the transferred release/archive SHA-256 and the approval
  package; native `visudo` policy parsing passed before administrator activation.
- Spark's host check passes. systemd-analyze emits a permission warning for an
  unrelated dashboard unit; the checked monitor units pass.
- Jetson's non-disruptive preflight passes. The installer stopped the old Web
  service before checking listener availability; installation and startup passed.
- Native dependency installation and imports use separate unprivileged check
  environments (Spark Python 3.12 / Jetson Python 3.10); packaged files remain intact.
- Baseline: all three Spark monitor units and both Jetson V2 units are active and
  disabled at boot. Health endpoints pass; the existing Jetson helper reports
  registered, active data PDU and verified data connectivity.

Staging directories on each device are under the SSH account's home:
`aoc-deploy/astryx-spark-0.2.0-20260923/` and
`aoc-deploy/astryx-jetson-0.5.0-20260923/`. Each includes release/archive checksums,
`approved.tar.gz`, `bootstrap.py` and `approve.sh`. The last script verifies pinned
archive/bootstrap digests, replaces only the matching old approval and runs verify.
It does not install or restart the applications.

## Approval boundary

The existing helper grants exact actions against a root-owned, hash-approved
payload. A changed release cannot be substituted through that allowance. See
[restricted maintenance access](../../deploy/maintenance/README.md).
Both devices require a password for general sudo; credentials are not requested
through chat or stored in scripts.

| Platform | New approval SHA-256 |
| --- | --- |
| Spark | `0c15110a3b26cd0a1206db5d491bae39dcca58c88cd02d486ced3cbef2f2cf49` |
| Jetson | `f1c013f979ba20b1f4fe5f16dfc32fc2defb9ba2dc2b7d779e7065257185e705` |

The administrator activated both staged approvals. Their digests were verified
before deployment and again after completion. Spark was deployed and checked
first, followed by Jetson, using the existing restricted `aoc-maintain` actions.

## Device results and limits

- Spark: all three monitor services are active; final health and collector status
  are `ok`. All 28 manifest-listed files match their hashes. The radio process ID
  remained unchanged throughout deployment, and all 12 Open5GS containers are
  healthy. No boot enablement was added.
- Jetson: both V2 services are active, disabled at boot and have zero automatic
  restarts. Web and device health are `ok`; all 48 manifest-listed files match.
  Fresh device evidence reports registration, active data session, verified
  RNDIS-bound data connectivity, matching lab policy and protected management.
- Both: the served HTML and two entry JS/CSS assets match the installed files;
  SPA routes return the app, and unauthenticated device APIs return 401. Dependency
  license notices are present in each installed frontend directory.
- Rollback: both helpers successfully restored the previous release, its current
  symlink was checked and its health endpoint responded successfully. The approved
  release was then reinstalled and checked again. Jetson device evidence was stale
  immediately after startup; the final fresh poll passed all connection checks.
- Backup checkpoints are managed by the installers: Spark uses
  `/opt/agentic-ocudu/monitor/previous.json`; Jetson uses
  `/var/lib/aoc-maintenance/jetson-rollback.json`, referencing its backup directory.
  The successful rollback exercised these checkpoints. Protected checkpoint
  contents and live database schema were not independently read through broader
  administrator access.
- Jetson `maintenance=false`, but `recovery_paused=true`: the executor's existing
  shutdown policy persists this flag on restart. Automatic fault recovery was
  enabled before deployment and is now paused; normal connectivity is verified.
  No recovery job or modem reset was issued to change that state.
- Authenticated live UI/SSE was not rechecked because no device login session was
  available. Local browser suites passed before deployment; device checks above
  cover health, installed assets, routing, authentication rejection and live UE
  evidence. These development builds still record `dirty=true`.

Question: can the new UI and Identity changes be deployed within the existing
maintenance permission? No CodeGraph index exists. The inspected call path is
`build_release → maintenance.build → bootstrap --check/replace-approval →
aoc-maintain approved/execute → platform installer`. Impact is a new approved
application payload; the role/account and exact sudo action list remain unchanged.

## Manifest SHA-256

- Spark: `d37822fdad93c2c5fe842411b32b2de348fefd7d218d3e8f4e01afcf83634a9e`
- Jetson: `75b3e589053d14429347a093e081c881f908b5bc63ae9b86408d905f993097eb`

Base source: `fd3b3b059b3e239912773d2c771c8fb5f64c5975` (`dirty=true`).
