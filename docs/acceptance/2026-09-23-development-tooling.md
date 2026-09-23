# Development tooling remediation — 2026-09-23

[简体中文](2026-09-23-development-tooling.zh-CN.md) ·
[Review baseline](2026-09-23-development-readiness.md)

## Question, paths and impact

Question: do the documented development, test and release entry points now
execute their promised work? No CodeGraph index exists in this checkout.

- `make install-dev -> venv/pip -> npm ci/build`: creates a selected isolated
  environment, checks Python 3.10–3.12, installs tools and both application
  dev requirements, and prepares both frontends. Existing environments are
  preserved; `VENV` selects a fresh location when necessary.
- `make check / CI -> test-stack -> tests/`: active Open5GS, resource
  preflight, radio and release-tool tests now run alongside application tests.
  Obsolete SQL/IMS deployment and removed one-time repair tests were moved to
  `archive/development-baseline-tests/`; no obsolete imports were restored.
- `make e2e-spark -> scripts/e2e_spark.py -> Spark API -> Playwright`: creates
  temporary authentication, database and synthetic observations, binds an
  inherited loopback socket and runs all three browser suites. The executor
  socket points inside the temporary directory. Failures propagate and the
  server is terminated in cleanup. It cannot invoke the installed stack helper.
- `make build-*-release -> scripts/build_release.py -> stage/download/verify
  -> archive`: builds the UI and selects Linux ARM64 CPython 3.10 or 3.12
  wheels, evaluating dependency markers for the target. Validation checks
  exact lock membership, wheel metadata/tags, Python and transitive dependency
  compatibility. Archives include version and source metadata, with an
  external SHA-256 file. Spark verification checks wheel checksums and its
  installer rejects the wrong host before modifying it.

Application APIs, modem operations and radio/core control behavior are
unchanged. These changes affect developer setup, CI and release construction;
they do not complete an installation or radio acceptance gate.

## Validation

- A new Python 3.11 environment successfully installed backend dependencies
  and both locked npm dependency sets. Both frontend production builds passed.
- `make check VENV=local/bootstrap-check`: Jetson 36 tests passed, Spark 51
  tests discovered with one macOS-only socket test skipped, root suite 116
  tests passed; TypeScript and documentation/release/license/shell audits passed.
- Eight release-tool regression tests cover target markers, explicit download
  selection, valid and incompatible wheel tags, internal metadata mismatch,
  incomplete/corrupt wheelhouses, dependency/Python requirements, and archive
  checksums/overwrite/symlink rejection. Spark has additional host rejection
  and wheel tampering tests.
- All three Spark Playwright suites passed on desktop and mobile: navigation,
  detail routing, authentication expiry/logout, evidence expiration, charts
  and responsive layout. This is synthetic browser evidence, not RF evidence.
- Both real offline archive builds completed with ARM64 wheels. The working
  tree is uncommitted, so manifests intentionally report `dirty=true`.

After explicit user authorization, source and locked wheels were transferred
only to new temporary directories on the two devices. Native offline installs
and `pip check` passed:

| Device | Native Python | Application tests | Root tests | Existing service health after testing |
| --- | --- | --- | --- | --- |
| Jetson | 3.10.12 | 36 passed | 116 passed | Web and device `ok` |
| Spark | 3.12.3 | 51 passed, no skips | 116 passed | Collector `ok` |

These runs reproduce the platform/backend and root test portions of the CI
matrix; GitHub Actions itself was not triggered. In particular, the socket
test skipped on macOS passed on Spark. Temporary environments used only
`pip --no-index` with the prepared wheelhouse and did not install system
packages or invoke production lifecycle actions.

Both archives were extracted into fresh local directories and passed their
included verifier. Archive SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| Jetson 0.3.0, release `619eb3735e7dfd91`, 14 wheels | `6dacb782dfb4c6ca7d7d95087d0e6f0e74f2adf9f790b7d261f993b607341fb6` |
| Spark 0.1.0, release `d987aca4396311d2`, 13 wheels | `da58c7c8414e9b44aca24d45e6ea280fd95e69915b4bbe5cbda91cf516fe4a3d` |

R06, P3-15/16/17 and P3-GATE remain open. No production package, service,
database, modem or route was changed. Actual install/rollback/reinstall and live radio fault injection remain
separate from these development and native unit-test results.
