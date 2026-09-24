# Contributing

## Workflow

Create changes on `feature/*`, `fix/*`, `release/*` or `hotfix/*` branches and
use Conventional Commits. Keep a pull request focused on one application or
one shared contract whenever possible. Describe the trigger, resulting
behavior, validation and rollback impact.

## Ownership boundaries

- Jetson application changes belong in `apps/jetson-console` and `deploy/jetson`.
- Spark application changes belong in `apps/spark-platform` and `deploy/spark`.
- Protocol-stack changes belong in `stacks/ocudu` or `stacks/open5gs`.
- Shared UI code in `packages/console-ui` must contain no platform logic.
- Retired material stays outside the current source tree and releases.

Do not add compatibility imports for retired paths. Update imports, tests,
release manifests and documentation in the same change.

## Documentation

Runtime interfaces use English. Current architecture, setup, operations,
troubleshooting and release documents have matching English and Simplified
Chinese files. Keep commands executable from the documented working directory,
use relative links for repository files, and mark unverified behavior clearly.

## Validation

Run the narrowest useful target while developing and `make ci` before review.
This runs both backend suites, shared stack/release tests once, both production
frontend builds (including TypeScript) and repository audits. Install backend
development dependencies first; the frontend builds run `npm ci` themselves.
Use Python 3.12 and Node.js 22 to match automatic CI. The existing `make check`
remains useful for checking an already prepared development environment.

Each PR runs one `Quick checks` job on Ubuntu 24.04. Merging does not trigger
another identical run; direct pushes to main are not automatically checked.
The `CI` workflow can also be run manually. Browser E2E and the Jetson Python
3.10/Spark Python 3.12 matrix move to the manual `Extended checks` workflow.
Run it for browser behavior changes or before releasing; it uses synthetic
services and does not operate hardware. Reduced automatic CI does not certify
browser behavior or Jetson Python 3.10 compatibility. Known E2E timing issues
remain visible in manual runs; this workflow change does not fix them.

The question is which checks are needed on every change. No CodeGraph index is
present. The path is `pull_request → CI → make ci`; optional validation is
`workflow_dispatch → Extended checks → backend tests / e2e-*`. Automatic checks
retain code, build and repository validation while removing browser startup,
duplicate shared tests and the post-merge rerun. Validate workflow syntax and
`make ci` when changing this contract. Hardware evidence belongs in
`docs/acceptance/` as a redacted summary; release validation is described in
[Releasing](docs/releasing.md).

Never commit credentials, subscriber identities, production addresses,
databases, logs, packet captures, generated releases or unredacted screenshots.
