# Review fixes — 2026-09-28

[简体中文](2026-09-28-review-fixes.zh-CN.md)

Follow-up: [hardware deployment and rollback acceptance](2026-09-28-review-deployment.md).

Source baseline: `5f2d06f9baa586fb1bff73ac9c7c0822d2d62b87`, with the
uncommitted fixes described here. Application versions remain Jetson 0.6.0 and
Spark 0.2.0. This is a local development record, not a deployed release.

The question was whether the confirmed findings from the
[second-pass review](2026-09-28-next-round-review.md) could be fixed without
device operations. There is no CodeGraph index; source inspection, call-path
tracing and regression tests were used. No device was connected, deployed to,
started, stopped or validated during this repair phase. No roadmap gate closes.

| Finding / call path | Change and impact | Regression evidence |
| --- | --- | --- |
| Jetson `cancel_job` → cancellation event → idle `sample(probes=True)` | Clear the cancellation event when no worker can perform terminal cleanup; ready/paused cancellation resumes normal idle probes and keeps recovery paused. | Both ready and normally paused tasks, repeated post-cancel probe samples. |
| Spark `ControlHandler` → `execute` / `request_cancel` → `persist` | Serialize status changes and atomic-file replacement under one reentrant lock; include initial progress in failure handling and reserve a job only after successful initial persistence. | Concurrent progress/cancel interleaving, initial progress-write failure, initial reservation-write failure and acceptance of the next job. |
| Diagnostics endpoint → `redacted_diagnostics` | Normalize identifier keys and redact structured observation values named by those keys. Live source snapshots remain unchanged. | Authenticated export with root/nested observations and `InvocationID`; nonsensitive metrics retained. |
| Scheduler payload → `parse_ocudu` → throughput aggregation | Preserve an explicit zero rate with zero transport blocks; missing or contradictory positive rates remain unavailable. MCS/BLER without blocks remain unavailable. | Active, idle, mixed, multiple-active and missing-field cases. |
| Source CLI → stack runtime → systemd callbacks; package stage → verify → install | Restore maintained lifecycle source under `deploy/spark/stack`, current units and offline private packaging. Remove the missing `scripts.v2` import; archive retired deployment inputs. | CLI help, exact manifests, ARM64 ELF/build provenance, tamper/link rejection, simulated install/rollback, owned-resource checks and failed-start/stop retention. |
| Spark browser parity navigation | Update the stale five-item expectation to the implemented eight-item navigation. | Full local Spark browser suite. |

Ready/paused task-level sampling exclusion was withdrawn as a confirmed defect
in the second-pass review and is unchanged.

Stack tooling supports a fresh installation only: it refuses existing releases,
units and CLI paths. Installation does not start/enable services or provision
subscriber data. The package is a private deployment candidate, containing its
input core configuration and credentials; it is not a public application archive.
Startup requires current SCTP ownership and successful NG Setup from infoAPI.
Initial radio telemetry is disabled until the separate guarded metrics setup.
See the [stack deployment guide](../../deploy/spark/stack/README.md).

## Local validation

Environment: macOS, Python 3.11.15 (`local/bootstrap-check`), Node 24.14.0.

- `make ci VENV=local/bootstrap-check`: both production builds/type checks,
  7 frontend behavior tests, 80 Jetson tests and 70 Spark tests (69 passed,
  one Linux peer-credential test skipped) passed. The shared suite initially
  hit a sandbox restriction binding a loopback HTTP port.
- Re-ran `make test-stack docs-audit release-audit license-audit shell-check
  VENV=local/bootstrap-check` with local listener permission: all 172 shared
  tests and all audits passed. Total Python result: 321 passed, one skipped.
- `make e2e-spark VENV=local/bootstrap-check` and
  `make e2e-jetson VENV=local/bootstrap-check` passed against local synthetic
  services; Jetson reported an empty failures list.
- Production builds retain existing bundle-size warnings; no build errors.

Install tests redirect all paths into temporary directories and replace
Docker/systemd/platform calls. ELF inputs are synthetic. They establish source
behavior, not target executability or radio readiness. No real release was
installed and no device rollback was attempted; simulated installer failure
removed only the new files. Real ARM64 artifacts, Python 3.10/3.12 and Node 22,
Linux service validation, existing-install migration, metrics commissioning,
N2/RF/UE connectivity and device rollback remain for a later authorized phase.
