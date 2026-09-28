# Next development review — 2026-09-28

[简体中文](2026-09-28-next-round-review.zh-CN.md)

Follow-up: [local repairs and validation](2026-09-28-review-fixes.md).
Findings below preserve the pre-fix review; device acceptance remains deferred.

Reviewed revision: `5f2d06f9baa586fb1bff73ac9c7c0822d2d62b87`, initially clean
`main`. Review covered both applications, shared UI, stack/deployment tools,
current documentation, local tests and the three supplied devices. There is no
`.codegraph/` index; source inspection and isolated reproductions were used.

The question is what can be trusted as the starting point for another development
round. The applications run, but the live 5G stack is currently stopped. Local
checks expose gaps that prevent treating this checkout as release-ready. This
record closes no [roadmap](../roadmap.md) gate.

## Second-pass verdict

At the user's request, the findings were challenged using normal-lifecycle
simulators, real Spark protocol handlers and pinned upstream source. The original
list was too categorical: **four code defects remain confirmed; one item is a P2
deployment-engineering gap; one is a design question, not a confirmed defect.**
No P1 finding remains in this review.

| Original finding | Revised judgment | Reason |
| --- | --- | --- |
| Stack rebuild chain | P1 → P2 engineering gap | Application staging/verification and Open5GS rendering work; project-specific lifecycle installation inputs are missing. |
| Jetson cancellation | Confirmed P2, narrower scope | Normal probe samples keep failing after cancellation; samples without probes can still succeed. |
| Jetson ready/paused observation | Withdraw confirmed-P2 classification | Task-level exclusion is explicit; expiry is correct; continuous observation during reserved tasks is not promised. |
| Spark concurrent cancellation | Confirmed P2 | Real concurrent protocol handlers reproduce the file race and stranded task without fabricated failures. |
| Diagnostics redaction | Confirmed P2 | The existing export contract explicitly excludes the identifiers that remain; this is not a credential leak. |
| Idle-UE throughput | Confirmed P2 | Zero is valid in the pinned upstream implementation; the adapter erases it and invalidates the sum. |

Spark's observed parity failure is a stale test expectation, not evidence of a
navigation defect. The intended eight-item navigation is documented and implemented.

## Current device baseline

Observations were taken around 09:15 Hong Kong time on September 28. Jetson A is
the first supplied Jetson; Jetson B is the second. SSH checks read selected service
properties, loopback application health, project-scoped container status, USB
product IDs and release hashes. Jetson `ue-status` used the existing restricted
maintenance helper, including its normal lock and audit bookkeeping. No service
start/stop, deployment, modem write, route change or new UE data probe was run.

| Evidence | Spark | Jetson A | Jetson B |
| --- | --- | --- | --- |
| SSH / architecture | Reachable / ARM64 | Reachable / ARM64 | Reachable / ARM64 |
| OS / Python | Ubuntu 24.04.4 / 3.12.3 | Ubuntu 22.04.5 / 3.10.12 | Ubuntu 22.04.5 / 3.10.12 |
| Application version | 0.2.0 | 0.6.0 | 0.6.0 |
| Release ID | `a4f6b8caf8f015af` | `9ed9fbcf1d68bf78` | `9ed9fbcf1d68bf78` |
| Manifest-listed files matching | 28/28 | 51/51 | 51/51 |
| Application services | All three active/running | Device and Web active/running | Device and Web active/running |
| Application restart counters | All zero | Both zero | Both zero |
| Public health | OK; collector OK | OK; device evidence OK | OK; device evidence OK |
| USB product present | B210 | RM520N-GL | RM520N-GL |
| Fresh UE registration / connected | Not independently correlated | False / false | False / false |
| Reported data PDU active | — | True | False |
| Management protected / recovery paused | — | True / true | True / true |

Spark's `aoc-v2-core.service` and `aoc-v2-radio.service` are inactive/dead.
The `aoc-v2-open5gs` project-scoped container query returned no containers,
including stopped ones; the bounded N2 HTTP check failed. Both Jetsons report
failed radio/registration/data-path health. Jetson A's residual active-PDU flag
does not establish connectivity. The reason or time of stack shutdown was not
established, and this review did not restart it.

This observation supersedes the running-state snapshot in the
[September 27 review](2026-09-27-next-round-review.md), while preserving the
[later deployment evidence](2026-09-27-ui-deployment.md) as historical acceptance.
Application health measures service/evidence availability, not 5G connectivity.

Jetson A also has two older non-V2 service units in failed state; both are disabled.
Their presence alone does not show a competing modem controller. On Spark the
inspected other-platform services are inactive, but its core and monitoring units
remain enabled at boot. Project application units are disabled; project core/radio
units are static. Reboot restoration and resource ownership remain unvalidated.
Management protection is reported by the application, not independently proven
for the actual overlay transport and policy-routing path in this review.

All application manifests still report `dirty=true` with source base `87e059f`.
Matching listed files proves consistency with those manifests, not equivalence to
a clean current checkout. Manifest SHA-256 values:

- Spark: `9c7bd2ce1425a0d52b11d632b5f7ac6fc374cf444a73996a23e17797e98036bf`.
- Both Jetsons: `004ce1c7a84910237ad06876ec199133118dbc761b9bdeaeba8087aef1cf87a0`.

## Findings, qualifications and required regressions

### P2 — Project stack lifecycle source and installation inputs are incomplete

`python scripts/aocctl --help` fails before argument parsing:
`ModuleNotFoundError: No module named 'scripts.v2.runtime'`.
[scripts/aocctl](../../scripts/aocctl) line 6 imports that missing implementation.
The application path is Web → executor →
[control.run_step](../../apps/spark-platform/backend/aoc_spark/control.py) lines
36–45 → installed `/usr/local/bin/aoc-v2ctl`. The lifecycle controller requires
V2 core/radio units, but their definitions are absent from the current tree.
`scripts/install_radio.py` (review-time path; subsequently archived) line 21 instead installs old
`aoc-stack`, `aoc-core` and `aoc-gnb` units and requires a previous launcher.

The current [Spark setup guide](../setup-bs-spark.md), lines 10–12 and 37, still
directs developers to the old image lock and stack templates. Those inputs contain
OAI/MySQL/IMS, whereas Open5GS has its own locks under `stacks/open5gs`.

Counterevidence limits the impact: `scripts/aocctl` is not part of the current
application packaging path. Temporary `monitor_release.stage + verify` succeeded
with 28 files and release ID `a4f6b8caf8f015af`; Open5GS `render()` also succeeded,
and the OCUDU binary build entrypoint exists. Application/stack separation is
intentional. The installed standalone start scripts operate existing V2 units
through the maintenance helper without invoking this broken repository entrypoint.

What remains missing is a traceable way to install the project-specific controller
and units on a clean host, or review an update to that controller. The formal
operations guide and Web executor still require the installed V2 CLI; no current
implementation, unit generator or declared external package supplies those files.
This is a P2 reproducibility gap, not an application-build failure or demonstrated
live controller fault. Restore that supported path within the declared directories
and archive retired tools; do not redirect the import to the old `scripts.aoclib.cli`.
Add CLI help, installation completeness and inert-service rehearsal checks for the
actual supported entrypoint.

### P2 — Cancelling a ready or paused Jetson job poisons later sampling

Path: Cancel → `cancel_job` → `sample(True)` → `check_cancel`.
[agent.py](../../apps/jetson-console/backend/aoc_jetson/agent.py) lines 453–460
sets the cancellation event and directly finishes a job with no live worker,
without clearing the event. Cleanup at lines 441–446 only runs through `execute`.
Both ready and paused jobs reproduced consecutive unavailable samples with
`Cancelled at a safe operation boundary`. The second pass used two real simulator
processes, authenticated FastAPI routes, Unix RPC and the normal serve loop without
assigning cached state or advancing time. Samples still failed 12 and 24 seconds
after cancellation and after maintenance was toggled on/off; evidence timestamps
advanced, ruling out merely reading stale cache. A restart restored one instance;
creating/completing a new job restored the other. The precise scope is
`sample(True)` when network quality permits the probe branch: `sample(False)`
can still succeed. This is not a failure of every AT query, but affects normal
healthy-network background polling.
Test cancellation followed by multiple idle samples and advancing SSE evidence,
without creating a replacement job. The browser test currently creates Recover
immediately after cancellation, masking the defect.

### Design question — Observation is suspended for the whole Jetson task

Path: `create` → ready, or `execute` → paused → `serve`.
[agent.py](../../apps/jetson-console/backend/aoc_jetson/agent.py) line 607 gates
all sampling on `not self.current`. Ready and paused jobs retain `current` even
without an executing worker. Normal API workflows in two real simulator processes,
waiting 23 seconds without clock or state manipulation, confirmed unchanged
evidence timestamps and stale quality in both states.

This alone is insufficient to establish a defect. The 20-second expiry correctly
withdraws a connected claim; the implementation deliberately serializes at task
level, and documentation does not promise observation while a plan is reserved.
The earlier confirmed-P2 classification is withdrawn. Decide whether the product
should explain this pause or allow observation while waiting. Only if continuous
observation is required should scheduling change, with hardware locking, no
concurrent serial access and no automatic recovery during manual work verified.

### P2 — Concurrent Spark cancellation can strand the operation reservation

Path: `ControlHandler` threads → `execute` / `request_cancel` → `persist`.
[control.py](../../apps/spark-platform/backend/aoc_spark/control.py) lines 68–78
uses one task-specific temporary filename, but `emit` does not hold the lock used
by cancellation at lines 119–128. A deterministic two-thread interleaving let
cancellation replace that file first; the initial execution emit then raised
`FileNotFoundError` outside its try block at line 90. No command executed, the
worker exited with `cancel_requested`, and the next operation was rejected as
`operation_in_progress`. Web recovery polling sees a nonterminal state indefinitely
in that executor process until external recovery; this is not irreversible.

The second pass used actual threaded `ControlServer` handlers over socketpairs;
only Linux peer-credential retrieval was substituted on macOS. Three subsequent
protocol queries retained `cancel_requested`, and a new run returned conflict.
The UI permits queued-task cancellation and Web returns before execution completes,
so the concurrent path is reachable. A further 100 trials without a persistence
patch or scheduling barrier produced six stranded tasks with run errors, sixteen
cancel-handler errors and 78 tasks marked failed by the race. These artificial
concurrency counts establish reachability, not production incident probabilities.

Serialize state updates and persistence, protect initial emission, and test actual
concurrent cancellation/progress with a terminal result and a subsequent operation.

### P2 — Spark diagnostic redaction misses observation values

Path: Diagnostics → `/api/v1/diagnostics` → `redacted_diagnostics(snapshot())`.
[web.py](../../apps/spark-platform/backend/aoc_spark/web.py) lines 33–43 filters
dictionary keys, while collector observations put `b210_serial`, `radio_pid` and
`b210_holder_pids` in `name` and their contents in `value`. `InvocationID` also
differs from the filter's `invocation_id`. Real login and the authenticated
diagnostics endpoint confirmed all four synthetic identifier types survived,
while an ordinary `pid` key was redacted. The pre-existing
[page acceptance contract](2026-09-12-v2-p2-07-pages.md), line 17, explicitly requires
removing PID, InvocationID and B210 serial numbers. This violates the export's
redaction promise; normal authenticated display is not the defect. No password,
SIM secret or authorization bypass is alleged.
Normalize names and redact observation values as well as direct keys; assert that
synthetic sensitive markers are absent from the complete exported JSON. No live
diagnostic export or credential disclosure was performed in this review.

### P2 — One idle UE hides aggregate radio throughput

Path: scheduler → `parse_ocudu` → collector → gNB charts.
[telemetry.py](../../apps/spark-platform/backend/aoc_spark/telemetry.py) lines
52–53 replaces explicit zero bitrate with null when transport-block counts are
zero; lines 73–77 require every UE bitrate to be non-null. A synthetic active UE
reported 23 Mbps downlink / 5 Mbps uplink. Adding a UE explicitly reporting zero
bitrate and zero blocks changed both totals to unavailable. Preserve explicit
zero traffic while retaining unavailable semantics for absent bitrate, MCS and
BLER. Test active/idle combinations and genuinely missing fields separately.

Counterevidence: `test_scheduler_units_unknown_cqi_no_blocks_and_epoch` explicitly
expects no-block bitrate to be unavailable; this is intentional behavior. However,
its fixture reports positive uplink bitrate with zero uplink blocks, rather than
the valid idle-zero case. In the pinned upstream commit, the
[scheduler calculation](https://gitlab.com/ocudu/ocudu/-/blob/050a2bb72e1d794cd60570d809987c1fcda3e54b/lib/scheduler/logging/scheduler_metrics_handler.cpp#L601)
divides transferred bits by report duration, yielding zero with no transferred
bytes; the [cell consumer](https://gitlab.com/ocudu/ocudu/-/blob/050a2bb72e1d794cd60570d809987c1fcda3e54b/apps/units/flexible_o_du/o_du_high/du_high/metrics/consumers/scheduler_metrics_consumers.cpp#L171)
sums UE rates including zero. The local recheck distinguished active-only,
active-plus-explicit-zero, missing-rate, idle-only and zero-with-failed-block cases.
Only a genuine missing rate justifies losing the complete sum. This remains a
data-semantics defect, not a radio fault or evidence that actual traffic stopped.

## Validation and release gaps

Local environment: existing `local/bootstrap-check`, Python 3.11.15 and Node
24.14.0. The default `.venv` is Python 3.9.6 and unsupported. These local versions
do not replace the Python 3.10/3.12 and Node 22 release matrix.

- `make check VENV=local/bootstrap-check`: Jetson 79 passed; Spark 64 passed and
  one macOS peer-credential skip. The shared suite first hit the sandbox's localhost
  bind restriction; `make test-stack` with loopback permission passed all 156.
- The remaining `make check` targets ran separately: both TypeScript checks,
  documentation, release, license and shell audits passed. Total Python outcome:
  **299 passed, one skipped**; all seven frontend behavior tests passed.
- Both production frontend builds passed using installed dependencies. The
  existing over-500-kB chunk warnings remain. No fresh dependency install or
  ARM64 package build was performed.
- `make e2e-jetson VENV=local/bootstrap-check` passed on the isolated simulator,
  including its 35-second stream check and desktop/mobile workflow checks.
- `make e2e-spark VENV=local/bootstrap-check`: `browser.mjs` and `information.mjs`
  passed; `parity.mjs` failed at line 298 because its expected navigation still
  contains five items while the intended UI has eight. Update the stale assertion
  and run the entire suite; later parity assertions were not certified by this run.
- Subscription maintenance still lacks complete apply/failure/restore coverage:
  partial insertion, lost acknowledgement, disk-full, cleanup failure and restore
  into an independent test volume remain to be exercised with synthetic data.

The earlier CFUN restoration, Web control EOF reconciliation, Spark listener
precheck, active-session filtering, history indexing and SSE lifetime fixes are
present. Jetson rollback now restores unit definitions in source; live rollback
acceptance is still separate. Do not reopen those fixed source issues as unchanged
findings or infer that they close hardware gates.

## Next development sequence

1. Restore the reproducible stack control/install chain and correct its setup
   documentation. Make the full browser baseline pass, including Spark parity.
2. Fix Jetson cancellation leakage and Spark cancellation persistence with isolated
   regressions. Correct diagnostics and idle-UE telemetry semantics. Decide the
   ready/paused observation requirement separately before changing task exclusion.
3. Build clean, traceable ARM64 application artifacts; exercise the target Python
   matrix and subscription failure/restore tests before expanding maintenance.
4. Establish independent management and resource ownership, then explicitly
   schedule live stack restoration and acceptance. Complete P3-15 fault cases,
   P3-16 installation–rollback–reinstallation on both Jetsons, R06 for both
   platforms' ARM64 releases, and exactly five P3-17 stop/start/reconnection cycles
   with one modem controller. Assess P3-GATE only after this evidence exists.

Keep the roadmap as the only completion checklist. This change adds only the
paired review and updates documentation navigation/current-state prose. It includes
no application fix, deployment, restart, rollback or new gate completion. Device
addresses, credentials, subscriber identities and raw operational output are omitted.
