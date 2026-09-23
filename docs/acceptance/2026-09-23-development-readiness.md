# Development readiness review — 2026-09-23

Reviewed source: `3ae3d76` on `main`; the working tree was initially clean.
This is a dated review, not a new task list or hardware acceptance gate.
[The roadmap](../roadmap.md) remains the task authority.
[简体中文](2026-09-23-development-readiness.zh-CN.md)

Follow-up: [development tooling remediation](2026-09-23-development-tooling.md).

## Scope and method

Question: can the current repository and installed systems support the next
development cycle, and which checks must precede deployment?

Reviewed architecture, roadmap, CI, test/build entry points, release scripts
and selected application entry points. No `.codegraph/` index exists in this
checkout, so source inspection used ordinary file reads. Device inspection
used read-only SSH commands, systemd properties, USB inventory, release
metadata and public loopback health endpoints. No service, radio, modem,
route, subscriber or remote configuration was changed. Private addresses,
credentials, identities and raw operational logs are omitted.

## Observed device baseline

| Item | Spark | Jetson |
| --- | --- | --- |
| OS / architecture | Ubuntu 24.04.4 / aarch64 | Ubuntu 22.04.5 / aarch64 |
| Python | 3.12.3 | 3.10.12 |
| Available root storage | Approximately 2.9 TB | Approximately 193 GB |
| Hardware detected | USRP B210 | Quectel RM520N-GL |
| Application | Three platform services active | Both V2 services active |
| Health | `status=ok`, `collector=ok` | `status=ok`, `web=ok`, `device=ok` |
| Listener | Loopback port 8877 | Loopback port 8878 |
| Boot policy | Platform services disabled | V2 services disabled |
| Installed release | `1fa5d5d7e6fd150d` | `cf2988ba2827ab78` |

Spark's radio service was active and 12 project core/data-network containers
reported healthy. Other workloads also run on Spark; resource isolation must
be considered during later performance comparisons. Jetson's old
`aoc-jetson-agent.service` and `aoc-jetson-web.service` remained failed and
disabled, while the V2 services reported success and zero restarts. This is
residual service state, not evidence that V2 is failing.

Both installed packages lack the `RELEASE-VERSION` file now emitted by the
builders. Jetson's manifest identifies base commit `88a4b4d` with `dirty=true`;
Spark's manifest does not identify a source commit. These deployments cannot
serve as acceptance evidence for current `main`. Health and USB discovery
also do not establish current UE registration, PDU, N2 or bidirectional data
connectivity. No authenticated UI, fresh UE probe or throughput test was run.

## Findings and affected paths

1. **P1 — Protocol-stack regressions are outside the green default check.**
   `Makefile:check` and CI run only the two application test directories.
   Root `tests/` contains stack/configuration tests that are not executed.
   A separate run discovered 116 tests with one failure and 12 errors. Ten
   errors plus the failure concern stale IMS assumptions in
   `tests/test_deployment.py -> scripts/aoclib/core.py`; another error is a
   missing retired helper imported by `tests/test_handoff.py`. One additional
   error is environment-specific: the selected interpreter lacks `sqlparse`.
   Classify supported stack tests versus historical tests, archive retired
   paths, and include supported stack coverage in CI. Do not restore obsolete
   imports or add IMS merely to satisfy stale tests.

2. **P1 — The documented ARM64 release workflow is incomplete.**
   `Makefile:build-spark-release -> deploy/spark/platform/build-release.sh ->
   scripts/monitor_release.py:stage/download` downloads wheels for the build
   host's interpreter/platform, without target flags or an ARM64/Python 3.12
   host guard. Building on this Mac can therefore produce unsuitable offline
   dependencies. Both platform builders stage directories but do not create
   the `.tar.gz` artifacts promised in the release guide. Jetson also requires
   a separately prepared wheelhouse. Define and enforce the build environment,
   validate wheel compatibility and produce documented archives before R06.

3. **P2 — Spark E2E can succeed without testing.**
   `Makefile:e2e-spark` references absent `scripts/e2e/spark.sh`. It prints a
   preview reminder and exits successfully. Actual browser coverage exists in
   `apps/spark-platform/frontend/tests/browser.mjs` but is not reached by this
   target. Connect the target to an explicit simulator/preview and make
   missing prerequisites distinguishable from successful test execution.

4. **P2 — The documented development bootstrap is insufficient.**
   `make install-dev` installs only `requirements-tools.txt` (`sqlparse`),
   omitting application dev requirements and npm dependencies. A fresh setup
   following README's two commands cannot reliably run `make check`. The root
   `.venv` here uses Python 3.9.6 and lacks FastAPI. Document supported Python
   versions, isolated environments and both frontend/backend setup steps.

## Verification results and limits

| Check | Result |
| --- | --- |
| `make check PYTHON=.venv/bin/python` | Failed importing FastAPI in Jetson API tests |
| `make check PYTHON=local/monitor-venv/bin/python` | Passed; Jetson 36 tests, Spark 49 discovered with one skipped |
| Both frontend `npm run build` commands | Passed using existing node_modules |
| TypeScript, documentation, release, license and shell audits | Passed |
| Root `unittest discover -s tests` in the existing monitor environment | 116 tests; one failure, 12 errors |
| `make e2e-spark` | Exit 0 without browser execution; not an E2E pass |

The fallback monitor environment is also Python 3.9.6; passing there is not a
substitute for the CI Python 3.10/3.12 matrix. The skipped Spark test is the
Unix-socket control-server test disabled on macOS. Dependency installation
from scratch, target ARM64 package installation, rollback and browser E2E
were not performed. Static audit success does not verify those properties.

## Recommended next sequence

1. Repair bootstrap, supported stack test coverage and E2E entry points;
   reproduce the baseline on Python 3.10/3.12.
2. Close the release-build gaps and record source revision, architecture,
   Python version and artifact checksums. Perform R06 and P3-16 with a verified
   previous-release recovery path, one platform at a time.
3. Complete P3-15 with simulator coverage followed by hardware evidence for
   serial contention, interface renaming, registration/PDU disagreement,
   residual addressing, task cancellation and login expiry. The relevant
   runtime boundary is `api -> Agent.dispatch/execute -> Modem/Network ->
   Store`; keep all modem access under the existing executor.
4. Complete P3-17: five bounded stop/start and fresh data-reconnection cycles,
   checking single modem ownership and management connectivity each time.
   Close P3-GATE only with fresh registration, PDU, RAN and bound bidirectional
   user-plane evidence, recovery and speed-test results.

This review adds documentation only. No roadmap item has been marked complete
and no application or deployment behavior has been modified.
