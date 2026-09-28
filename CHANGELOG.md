# Changelog

## Jetson Console 0.6.0 / lifecycle improvements (unreleased)

- Correct local-state filters, persistent operation feedback and retained-history access in both Astryx consoles.
- Prioritize radio health and traffic, share chart queries, expose operations in navigation, and add responsive Setup assessments.
- Restore saved Jetson systemd unit files and reload systemd before starting the rolled-back web service.
- Index retained Spark metric names during ingestion; backfill schema 6 before monitor startup so history menus avoid scanning all samples.
- Keep Spark live streams open instead of closing every 15 seconds; recheck sessions before publishing and retain bounded service shutdown.

- Restore modem power once after an uncertain CFUN=0 result, preserving task failure and revoking temporary restoration authorization.
- Reconcile Spark control tasks after executor EOF without repeating the requested operation.
- Reject foreign or unverifiable Web listeners before Spark startup changes, using kernel cgroup ownership.
- Replace cross-service takeover with independent commissioning through the installed runtime.
- Prepare journaled data routes and resume observation on start; clean up owned routes on stop, including after device loss.
- Keep management Wi-Fi as the preferred default and reject route/resource conflicts without modifying external services.
- Package Jetson lifecycle scripts and distinguish service, observation and connection readiness.
- Require N2 NG Setup in Spark full-stack startup, and correct paired installation and operations guidance.

## Jetson Console 0.5.1

- Keep authenticated status streams open, recheck sessions for each update and bound graceful shutdown.
- Run independent read-only network probes concurrently to reduce status age without relaxing freshness limits.
- Distinguish stale device evidence from lost live updates in the Astryx UI.

## Jetson Console 0.5.0 / Spark Platform 0.2.0

- Use official Astryx Core, Neutral and Charts across both consoles, with responsive navigation, readable tables and evidence-aware history charts.
- Display complete numeric Spark subscriber identities in the authenticated UI; simplify subscriber inventory and preserve diagnostic/event redaction.
- Reset Jetson passive-rate baselines when interface identity changes or sampling fails.
- Include browser dependency license text in built frontend releases.

## Jetson 0.4.0 / connectivity-only data network

- Separate network access, observed lab selection and diagnostic configuration; migrate schema 2 with backups.
- Report registration, PDU, verified data, lab match and protected management independently.
- Add bounded automatic recovery after natural recovery wait; diagnostic failure alone never resets a modem.
- Remove active throughput UI, API/executor tasks and ext-DN server; preserve passive counters and historical records.
- Replace ext-DN with a pinned small HTTP health endpoint and add migration, recovery and four-page browser checks.
- Update and restore inner/outer release manifests together during connectivity upgrades; verify protected existing releases before reinstalling after rollback.
- Add exact role-specific passwordless maintenance with reviewed payload replacement and failure restoration; verify deployment and rollback on both devices.


## Unreleased

- Completed development bootstrap, added supported stack tests to default checks
  and CI, and connected Spark browser checks to an isolated synthetic server.
- Added Linux ARM64 offline archives with target-specific wheel validation,
  source metadata and SHA-256 files for both applications.
- Archived obsolete IMS/core and one-time repair test fragments.
- Reorganized the repository around independently owned Jetson, Spark, radio,
  core-network and deployment components.
- Replaced historical planning material with a self-contained documentation
  set and automated documentation boundary checks.
- Added paired governance, architecture, setup, operations, troubleshooting and
  release documentation.

## Jetson Console 0.3.0

- Added an independent Jetson console with bounded modem and network helpers,
  verified data-path status, task persistence and throughput testing.

## Spark Platform 0.1.0

- Added an independent Spark monitoring platform with OCUDU and Open5GS
  adapters, evidence-quality semantics, history, events and bounded operations.
