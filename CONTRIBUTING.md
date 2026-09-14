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

Run the narrowest useful target while developing and `make check` before
review. Frontend or release changes also require their corresponding build
target. Hardware evidence belongs in `docs/acceptance/` as a redacted summary.

Never commit credentials, subscriber identities, production addresses,
databases, logs, packet captures, generated releases or unredacted screenshots.
