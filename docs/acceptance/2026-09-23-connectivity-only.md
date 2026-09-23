# Connectivity-only development round

## Question and scope

Can UE access be independent of a fixed Spark management endpoint/cell identity,
while retaining lab selection checks and removing active throughput features?
Scope remains OCUDU + Open5GS. This checkout has no `.codegraph` index; source
and call paths were inspected directly. Previous engineering fixes remain included.

## Call paths and impact

- `config.validate` validates access, observed selection, diagnostic and recovery
  fields separately; installer `install -> backup -> migrate -> validate` upgrades
  schema 2 to 3 without discarding the old band/PCI reference.
- `Agent.sample -> Modem.snapshot / Network.snapshot / Network.probe` separates
  registration/PDU/data verification from lab and management checks. Changed
  session/interface evidence and expired or incorrectly bound probes invalidate
  data claims. Current management protection remains necessary for modem writes.
- `Agent.auto_reconcile -> create(recover) -> launch -> execute` waits for natural
  recovery, limits attempts and retains cooldown across restarts. Diagnostic-only
  failure never resets the modem. Cancellation pauses automatic recovery.
- UI has Overview, Device Setup, History and Settings. API request validation,
  task creation, launch and execution reject retired speed operations. SQLite
  upgrade backs up history and retires unfinished old jobs. Passive counters remain.
- `render -> runtime.connectivity_server / health` replaces ext-DN throughput
  service with fixed small HTTP health responses. `verify_bundle` checks N6 using
  bound ICMP/HTTP. `upgrade_connectivity` backs up and updates only owned ext-DN
  bundle files/service, restoring them if recreation fails.
- Old SQL/IMS UE acceptance and core throughput smoke tools/tests moved to
  `archive/development-baseline-tests`. The 36 legacy UE tests are not current
  regression coverage. Historical acceptance records remain unchanged.

## Validation

- Jetson backend: 42 tests passed locally and on Jetson Python 3.10.12.
- Spark backend: 51 tests on Spark Python 3.12.3, all passed; local macOS suite
  has one existing Linux peer-credential skip.
- Shared tests: 80 passed on both devices; three additional ext-DN upgrade
  preservation/rejection/rollback tests passed locally after the native run.
- Four-page desktop/mobile browser checks cover setup persistence/cancellation,
  recovery, missing speed navigation, CSRF, stale SSE and session expiry.
- Frontend builds/types, documentation, release, license and shell audits pass.
- Offline target wheel installation and `pip check` pass on both devices.
- Spark disposable `aoc-v2-corecheck-connectivity`: all 12 services healthy,
  eight NRF associations and PFCP established, UPF-local N6 ICMP/HTTP passed,
  all shutdown codes zero and database survived recreation. Test containers,
  network and volume were removed. This is not UE/GTP or RF evidence.
- Pinned ARM64 connectivity image:
  `sha256:45fc43f140364eab399b351d5672e9501279669acf2d9420360f8d28a2f87d31`.
  Its isolated image smoke confirms `iperf3` is absent. Other workloads' packages
  and services were not removed.

## Release and hardware acceptance

Jetson 0.4.0 release `0826938fd08ae477` and Spark 0.1.0 release
`d987aca4396311d2` are installed. The checkout is uncommitted (`dirty=true`).
Both devices passed passwordless approved-payload verification and service checks.
The sudo policy permits exact role-specific operations and stores no password.

- Jetson application installation/startup passed. Five application stop/start
  cycles passed the serial startup guard and regained fresh registration, PDU and
  bound data evidence in 20.58–33.50 seconds. These did not reconnect the modem.
- Spark application installation, previous-version rollback and reinstallation
  passed. Production ext-DN now serves fixed HTTP health responses without
  `iperf3`; all 12 core services are healthy.
- The first radio restart exposed a defect in the ext-DN updater: it changed the
  inner core files without updating outer `release.json` hashes. Startup rejected
  the mismatch. The updater now validates, backs up, updates and restores both
  manifests together. The operator ran the reviewed one-time repair successfully,
  preserving an original manifest backup and tightening group-write permissions on
  root-owned `bin`, `units` and `core/config` directories. Radio startup and a later
  complete core/radio restart both passed the integrity checks.
- With automatic recovery paused, one radio stop/start did not restore UE data
  within 150 seconds. A subsequent manually requested recovery task completed and
  restored verified registration/PDU/data. This failed natural-recovery sample is
  retained; it is not counted among the five successful cycles below.
- With automatic recovery enabled, five consecutive radio stop/start cycles each
  showed registration loss followed by registration, PDU and bound data recovery
  without manual intervention. Recovery times were **54.25, 25.00, 25.74, 57.68
  and 20.35 seconds**. No recovery-task pause transition was observed in these
  cycles; they do not establish that automatic CFUN retries executed.
- One Open5GS core stop/start with its dependent radio restarted passed. UE
  registration and data recovered naturally in **77.94 seconds**, with automatic
  recovery paused. All 12 services returned healthy. The same subscriber database
  volume and creation timestamp were retained, and UE registration succeeded.
- Management used SSH through Spark directly to Jetson Wi-Fi, with the return
  route verified on Wi-Fi. Tailscale itself still preferred the experimental data
  path. Across the five successful radio cycles, 356 persistent heartbeat samples
  had a maximum gap of **2.05 seconds**; the core test's 109 samples had a maximum
  gap of **1.21 seconds**. Old Jetson controllers were not running and the current
  serial startup guard had passed.

A separate early automatic-mode attempt was interrupted by concurrent read-only
maintenance queries contending for the helper lock. The harness restored radio
service and was updated to retry only those lock-busy read operations. That attempt
is excluded from the five completed cycles. Stale UE evidence was reported as
unknown during outages; independent Wi-Fi heartbeats were used to distinguish
stale modem sampling from actual management loss.

## Installation follow-up and final state

The earlier approved Jetson installer refused an existing release directory,
preventing safe reinstall after a rollback. The deployed fix now checks the exact
packaged files, all runtime ownership/permissions, and installed dependencies
before reusing that release. Unexpected source, writable runtime and invalid links
are rejected; a dependency-check failure preserves the existing release. The new
read-only verifier passed against the actual installed Jetson release as an
ordinary user. Jetson backend tests now total **45 passed**; shared tests total
**102 passed**, including maintenance approval replacement and failure restoration.
Documentation/release audits pass. Runtime backend code is unchanged by this
installer follow-up, so the radio observations above apply to the same backend.

Reviewed maintenance approval updates are activated on both devices and passed
native archive/`visudo` checks and passwordless verification.
The bootstrap requires the explicit previous approval digest, verifies its
protected files, preserves the exact account/role/sudo policy, serializes with
maintenance operations and backs up/restores access files on activation failure.
Jetson rolled back from `9a505b4a55d75f1b` to the previous release
`cf2988ba2827ab78`, installed and started `0826938fd08ae477`, rolled back again,
then successfully reinstalled and started the same existing `0826938fd08ae477`
release. Both rollback checks showed a healthy web service and the intentionally
stopped device executor; both subsequent startups passed the serial guard and
restored verified registration, PDU and data. The final recovery task completed,
with maintenance off, management protected and automatic recovery enabled.

Spark's newly approved connectivity updater also completed in production, passing
inner and outer manifest verification. Only ext-DN was recreated; the other core
containers and radio process remained running. All 12 core services were healthy,
and the running ext-DN contained no `iperf3` executable.

Five forced modem power/reset cycles and automatic retry-budget exhaustion have
not been demonstrated by the radio stop/start tests.
