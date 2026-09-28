# Review-fix deployment — 2026-09-28

[简体中文](2026-09-28-review-deployment.zh-CN.md)

Status: all three applications upgraded, rolled back and reinstalled successfully.
Final joint stability observation passed (65.35 seconds, seven samples).
Source baseline is `5f2d06f9baa586fb1bff73ac9c7c0822d2d62b87` plus uncommitted
[review fixes](2026-09-28-review-fixes.md) and matching patch-version updates.

## Candidate identity

| Candidate | Release ID | Manifest SHA-256 |
| --- | --- | --- |
| Jetson 0.6.1, ARM64 Python 3.10 | `b5e49d56a0e5eadb` | `bb96fa8d13c7729e910e0547883e2b97a62040c73c8b458fb990a4c1a179e27b` |
| Spark 0.2.1, ARM64 Python 3.12 | `ed2fc576489b02de` | `9476847225d96e5c3fc121c3acdc0f77c32b427da5ebc57f76fa32207663afa2` |

Maintenance approvals: Jetson
`418de2c2ecbc031da10020cd262d7657a4ebe40627f9a5b200efd36526c6703e`;
Spark `b5b76c580a8091fe2c3335540fc522ee6df25b7b3767555270a29b6a240ac5c6`.
Both packages are explicitly dirty development candidates. No clean release or
GitHub workflow execution is claimed.

## Completed checks

- Built both ARM64 offline archives using SHA-256-verified official Node 22.22.0.
  The installed Homebrew Node 22 could not start because a dynamic library was
  missing; the portable runtime avoided changing the host installation.
- Local checks: 321 Python tests passed, one Linux-only test skipped; seven
  frontend behavior tests passed. Production builds, both local synthetic
  browser suites and documentation/release/license/shell checks passed.
  Loopback tests required execution outside the local network sandbox.
- All three devices received only explicit deployment artifacts. Transfer
  checksums, package verification and native sudoers-policy checks passed.
- Spark: ARM64 Python 3.12.3, 36 targeted tests passed, including the real Linux
  peer-credential protocol test, concurrent persistence, diagnostic redaction
  and throughput aggregation. Native application unit verification passed;
  systemd also reported a permission warning for an unrelated dashboard unit.
- Each Jetson: ARM64 Python 3.10.12, 19 agent tests passed, including ready/paused
  cancellation. Upgrade prerequisites passed; the listener check remains for
  the installer after it stops the existing Web service.
- Target regressions ran in isolated user-owned virtual environments using
  packaged backend files and synthetic fixtures. They did not touch the live
  modem, databases, services or existing Python environments.

The first Jetson initially timed out over SSH, then recovered after the operator
confirmed it was powered on. Current live baseline has all three applications
running, all 12 Spark core containers healthy and both Jetsons connected with
verified modem-bound data paths. This supersedes the stopped-stack observation
in the earlier review; no restart was performed to obtain this baseline.

## Hardware deployment and rollback

The operator activated the exact approval on all three devices. The agent verified
those digests before installation; no sudo policy expansion was performed.
Operations were sequential: Spark first, then Jetson A, then Jetson B.

| Device | Final version / release | Previous version / release restored during rollback | Verified packaged files |
| --- | --- | --- | --- |
| Spark | 0.2.1 / `ed2fc576489b02de` | 0.2.0 / `a4f6b8caf8f015af` | 28/28 |
| Jetson A | 0.6.1 / `b5e49d56a0e5eadb` | 0.6.0 / `9ed9fbcf1d68bf78` | 51/51 |
| Jetson B | 0.6.1 / `b5e49d56a0e5eadb` | 0.6.0 / `9ed9fbcf1d68bf78` | 51/51 |

Each device completed install → old-version rollback → candidate reinstallation.
Spark restored the installer's saved application/database checkpoint and passed
old-version health and file verification. Both Jetsons restored their saved
application/configuration/database/unit checkpoint, started the old executor and
passed fresh registered/PDU/modem-bound data checks before reinstalling 0.6.1.
Final starts again produced fresh connected evidence. SSH remained available
through these operations, and both devices reported management protection.

Spark rollback took 45.68 seconds; candidate reinstallation took 23.83 seconds.
Jetson A install/rollback/reinstall took 17.52/7.19/14.12 seconds; Jetson B took
19.77/6.62/12.31 seconds. These include SSH and are operation durations, not
cellular registration latency.

- Spark radio/core service PIDs and monotonic start timestamps match the pre-upgrade
  baseline; all 12 project containers remain healthy. No protocol-stack restart,
  subscriber import, modem reset or recovery job was issued.
- Live HTTP index and primary JS/CSS hashes match each installed manifest; CSP
  frame protection and `nosniff` are present. Unauthenticated protected API reads
  return 401. Authenticated browser/SSE interaction was tested on the local
  synthetic server, not replayed against live user sessions in this phase.
- Application units remain disabled at boot. Both Jetson executors run with
  observation enabled and automatic recovery paused. Jetson B had recovery enabled
  before deployment; the normal `start` lifecycle intentionally leaves it paused.
- The first Spark post-rollback health read timed out at 10 seconds; a subsequent
  read succeeded without another service operation, with unchanged PID/restart
  count. Jetson A's first post-install read preceded the Web listener and was
  refused. Later observations used a bounded 30-second read-only health wait.
  Immediately after executor starts, `stale` evidence was not counted as success;
  fresh connected evidence was checked separately on both old and new versions.

## Boundary and remaining work

This accepts the two existing Jetson installations' upgrade, previous-version
rollback, reinstallation and management-connection retention (V2-P3-16).
The broader fault matrix, five-cycle endurance and P3 gate remain open.
The final 65.35-second joint observation passed all seven samples: 12 healthy
containers, one successful NG Setup, two registered/connected UEs, two active PDU
sessions with distinct addresses, and two verified N3 paths. Both Jetsons had
fresh modem-bound data evidence throughout; maximum evidence age was 13.94 seconds,
and each device supplied seven distinct evidence timestamps. All application
services ended active with zero restart counters. Final package hashes matched.
The applications and existing radio/core remain running.

Existing Spark radio/core and site-specific guard/CPU settings are outside the
application packages and were not replaced. The new stack installer supports
fresh hosts only; this run does not claim fresh stack installation or full-stack
stop/start validation. No RF configuration was changed. Package tests and target
regressions using synthetic inputs remain distinct from live connectivity evidence.

An initial broad source-snapshot transfer was rejected by automatic approval
review and was not executed. The accepted preparation used deployment-only
archives and four explicitly selected synthetic regression files with test
wheels. No production credentials, private configuration or logs were committed.
Private preparation evidence is under ignored `local/review-deployment-20260928/`.
