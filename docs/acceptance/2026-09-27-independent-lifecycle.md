# Independent OCUDU lifecycle development validation

Date: 2026-09-27. Source base: `39dde4d0216dee973ed6cbf40ecb500e83c1ac74`
plus uncommitted lifecycle changes. Jetson source/candidate version: 0.6.0.
This is development validation, not a new hardware deployment acceptance.

## Review question and call paths

Can OCUDU install, commission, start, inspect and stop its own components
without a separate project's preparation scripts or service names?
No `.codegraph/` index was present. Inspection followed these paths:

- `install-jetson.sh` → `manage.py install`: the wrapper already selects the
  install action; the previous setup guide passed an extra action.
- `manage.py commission` → installed Python → hardware discovery, network
  prerequisites and SIM fingerprint: system Python must not import offline
  modem dependencies, and commissioning must not stop another controller.
- Jetson `platformctl.py start` → maintenance helper → `manage.py start` →
  network helper → device RPC: starting units alone previously left observation
  paused and relied on pre-existing probe routes.
- `manage.py stop` → own units → route journal: cleanup must work after device
  loss and must not delete an administrator's route.
- Spark `platformctl.py start/status` → core health, radio and AMF gNB infoAPI:
  a running gNB process alone does not establish N2 readiness.

## Resulting behavior and impact

Installation, commissioning and routine operation now have separate documented
commands. `commission` replaces takeover and automatically selects the installed
runtime. It checks serial ownership, binds the site's SIM and management settings,
and leaves device services stopped. It performs no modem configuration writes.

Start validates Wi-Fi as the preferred IPv4 default and the configured Spark
route through Tailscale. Site NetworkManager profiles remain an explicit initial
prerequisite. OCUDU prepares only missing configured UPF, ext-DN and public-probe
host routes through the modem. Existing valid routes are reused without ownership;
conflicting host routes fail before additions. Atomic, private intent records and
numeric protocol matching distinguish owned routes from uncertain mutations.
Stop removes only exact owned routes, including after the interface disappears.
Changed or uncertain routes require inspection instead of automatic deletion.

Start resumes observation with automatic recovery paused. Repeated start preserves
an already running observation session. Service availability and fresh device
connection evidence are separate status fields. Spark start waits for one successful
N2 NG Setup before starting monitoring. It does not require a UE to be registered.

The Jetson verified release now includes the start, stop and status controller
scripts. An upgrade must update the application, its approved maintenance bundle
and operator shortcut copies together. No public API was added; runtime text is
English. Setup and operations documentation is paired English/Simplified Chinese.

## Validation

| Check | Result |
| --- | --- |
| `make test-jetson-backend VENV=local/bootstrap-check` | 72 passed |
| `make test-stack VENV=local/bootstrap-check` | 150 passed |
| Jetson frontend build, including TypeScript check | Passed; existing large-chunk warning remains |
| Documentation, release-boundary and shell audits | Passed |
| Candidate manifest verification | All 51 files match |
| Real Linux route integration | Passed in a disposable isolated container |

The first project-test attempt could not bind a local test HTTP port inside the
sandbox. Re-running with permission to bind the port passed all 150 tests.

`tests/integration/jetson_routes.py` ran on the Spark host in an existing ARM64
validation image, with `--network none`, `NET_ADMIN`, a read-only filesystem and
temporary code/state filesystems. It had no host mounts or modem devices. Only
modem discovery was substituted; kernel route additions, numeric readback, locking
and journal persistence were real. The cases covered prepare, repeated prepare,
preserving an existing route/default, rejecting a conflict or changed owned route,
and cleanup after the dummy modem interface disappeared. The container exited
successfully and was removed with `--rm`; deployed services were not operated.

Candidate release: `8ade791a3317ad5e`, ARM64 CPython 3.10, with reused and revalidated
locked offline dependencies. Manifest SHA-256:
`e297880d5a4ac2ec4f04395efbf76e113d7e61c62a977c62a8f0edee1340ae40`.
Application archive SHA-256:
`ffab1caae9f4bf916999c68028edae3ad344b7ca6fffe20b587e2bd5da546e0e`.
Matching maintenance bundle SHA-256:
`0b30462ac4a898a8c5f398114f682bdc0fc0c4a8acab826ef51597734329d127`.
Local candidate artifacts are under ignored `local/independent-lifecycle-20260927/`.

## Deployment boundary

At completion of this development-only validation, the candidate had not been installed on either Jetson. Spark's revised lifecycle
script has not been installed. Fresh hardware installation, upgrade, real serial
exclusion, dual-device registration, actual Tailscale transport and stop/start
acceptance remain to be verified against this candidate. Earlier 0.5.1 acceptance
does not certify 0.6.0. No deployed application rollback was needed or performed.
Subscriptions and deployment configuration were not changed by this work.

Subsequent deployment and bounded hardware results are recorded separately in
[0.6.0 hardware validation](2026-09-27-independent-lifecycle-deployment.md).
