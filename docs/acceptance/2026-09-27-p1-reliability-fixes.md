# Three P1 reliability fixes — 2026-09-27

[简体中文](2026-09-27-p1-reliability-fixes.zh-CN.md)

Source base: `87e059fd5b4010384606eca6180bd0f3ecc86aa1` plus these uncommitted
changes. Application versions remain Jetson 0.6.0 and Spark 0.2.0. This is source
and local regression evidence, not deployment or hardware acceptance.
Subsequent packaging, device rollout and bounded hardware checks are documented
in the [deployment record](2026-09-27-ui-deployment.md); the evidence below
describes the original source-fix stage.

## Question, paths and impact

Question: can the three P1 failure paths from the
[development review](2026-09-27-next-round-review.md) be handled without leaving
the modem switched off, retaining an abandoned control task, or changing the stack
before detecting a foreign Web listener? There is no CodeGraph index; source and
tests were inspected directly.

- `Agent.execute → Agent.write → Modem.write(cfun0)`: after commissioning and SIM
  verification, authorize one power-restoration attempt before sending CFUN=0.
  An exchange/readback failure attempts CFUN=1 while the caller holds the hardware
  lock, even if task cancellation was requested. The original error still fails
  or cancels the task. Failed restoration is explicitly reported; every CFUN=1
  attempt clears temporary authorization. No power-off retry is added, and failed
  management/identity checks do not trigger compensation. This covers both setup
  and recover callers. Physical restoration cannot be guaranteed if transport or
  hardware also rejects the compensating command.
- `POST /control → run_control → control_messages → poll_control`: normal EOF
  without a terminal response now follows the existing recovery-query path.
  It queries the original task ID and never sends another run command. Unknown
  tasks and unavailable executors become interrupted; completed tasks keep their
  terminal result. Releasing the API reservation does not prove the original
  systemd operation did not execute.
- `start.sh → Controller.start → check_web_listener → maintain`: before the first
  mutation, read kernel cgroup ownership for all IPv4/IPv6 listeners on the Web
  port. Existing listeners must all match the active Web unit's `ControlGroup`,
  and its health must be OK. Foreign/unknown owners or inspection failures stop
  startup without changes. A healthy owned listener retains idempotent startup.
  This precheck does not reserve a socket or serialize independent administrator
  actions after inspection. The Jetson lifecycle port guard is outside these
  three selected fixes.

## Validation

New regression tests reproduced the CFUN and executor EOF failures before the
fixes and pass afterward. Coverage includes lost CFUN acknowledgement/readback,
failed restoration, one-attempt authorization, identity rejection, setup/recover,
cancellation, management rejection, EOF before any message or after running,
terminal results, unavailable executors, foreign/unknown/multiple listener owners,
IPv6 wildcard listeners, stopped-unit ownership, inspection failure, unhealthy Web
and existing lifecycle idempotency.

Narrow suites passed: Jetson backend 79; Spark backend 57 including one existing
macOS Unix peer-credential test skip; lifecycle 42. The changes add 17 test methods.
`make ci VENV=local/bootstrap-check` also passed: Jetson 79, Spark 57 (one skip),
shared stack 156, totaling **291 passed and one skipped**. Both production frontend
builds, TypeScript checks, documentation, release-boundary, license and shell audits
passed. Existing frontend bundle-size warnings remain. Validation used local
Python 3.11.15 / Node 24.14.0; target Python 3.10/3.12 and browser E2E were not run.

A read-only query on Spark confirmed the SSH user can obtain the installed Web
listener's cgroup with `ss --cgroup`; no additional privilege was granted. No
service, modem or route change ran on any device. Installed binaries and lifecycle
scripts still need a reviewed release/update before these fixes affect hardware.
No ARM64 package, release checksum, rollback or roadmap gate is claimed here.
