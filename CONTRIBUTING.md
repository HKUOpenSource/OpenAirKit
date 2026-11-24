# Contributing

[简体中文](CONTRIBUTING.zh-CN.md)

## Workflow

Create changes on `feature/*`, `fix/*`, `release/*` or `hotfix/*` branches and
use Conventional Commits. Keep a pull request focused on one application or
one shared contract whenever possible. Describe the trigger, resulting
behavior, validation and rollback impact.

## Ownership boundaries

- Jetson application changes belong in `apps/jetson-console` and `deploy/jetson`.
- Spark application changes belong in `apps/spark-console` and `deploy/spark`.
- Protocol-stack changes belong in `stacks/ocudu` or `stacks/open5gs`.
- Shared UI code in `packages/console-ui` must contain no platform logic.
- Files under `archive/` stay outside imports, builds, and releases.

When moving or removing modules, update imports, tests, release manifests, and
documentation in the same change rather than adding compatibility shims.

## Documentation

Runtime interfaces use English. Architecture, setup, operations,
troubleshooting and release documents have matching English and Simplified
Chinese files. Keep commands executable from the documented working directory,
use relative links for repository files, and mark unverified behavior clearly.

## Validation

Run the narrowest useful target while developing (`make docs-audit`,
`make test-jetson-backend`, `make test-spark-backend`, or `make test-stack`) and
run `make ci` before opening a pull request. `make ci` runs both backend test
suites, shared stack/release tests, frontend TypeScript checks and production
builds, and repository audits (`docs-audit`, `release-audit`, `license-audit`,
`version-audit`, `shell-check`). See the [Developer Guide](docs/development.md)
for local preview servers, simulation mode, and browser E2E setup, and review the
[Architecture Decisions](docs/adr/README.md) before modifying console boundaries.

Install backend development dependencies first (`make install-dev`); frontend
builds invoke `npm ci` automatically. CI targets Python 3.12 and Node.js 22.
Use `make check` to run all local checks against an already prepared environment
(pass `VENV=local/dev-venv` if your virtual environment lives in a custom path).

- **Automatic PR gate (`Quick checks`)**: Runs `make ci` on Ubuntu 24.04 for
  pull requests.
- **Manual verification (`Extended checks`)**: Runs the multi-version matrix
  (Jetson Python 3.10, Spark Python 3.12) and synthetic browser E2E suites via
  `workflow_dispatch`. Run this workflow before releases or after frontend
  behavior changes; synthetic E2E runs do not operate physical hardware.

Hardware acceptance summaries belong in `docs/acceptance/` only after strict
redaction; release packaging rules are documented in [Releasing](docs/releasing.md).

## Optional Developer Tools

When `.codegraph/` exists at the repository root, contributors can follow the
[CodeGraph workflow](docs/coding-agent-codegraph.md) to trace symbols and call
paths before editing.

Never commit credentials, subscriber identities, production addresses,
databases, logs, packet captures, generated releases or unredacted screenshots.
