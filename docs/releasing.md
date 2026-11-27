# Releasing

[简体中文](releasing.zh-CN.md)

**Jetson Console** and **Spark Console** share the unified repository version
(`1.1.0`, defined in the root `VERSION` file) while maintaining independent
source boundaries and offline release archives. Cut and audit one platform
release at a time.

## Versioning Policy (SemVer)

OpenAirKit follows **Semantic Versioning 2.0.0** (`MAJOR.MINOR.PATCH`):

- **`MAJOR` (`X.0.0`)**: Breaking API, configuration schema, database layout, CLI, or deployment topology changes that cannot upgrade cleanly in place.
- **`MINOR` (`1.X.0`)**: Backward-compatible new capabilities, protocol stack or RF baseline upgrades, new console/AI-RAN features, and major performance milestones.
- **`PATCH` (`1.1.X`)**: Backward-compatible bug fixes, security hardening, installer/rollback fixes, audit refinements, and documentation corrections.

## Release Boundary Policy

Every release archive must pass the following boundary checks:

- **Single-platform isolation**: Each package bundles only its own
  application code, deployment tooling, locked Python/Node dependencies,
  wheelhouse, version metadata, integrity manifest, and third-party license
  notices.
- **Excluded artifacts**: Automated audits reject files belonging to the peer
  platform, `archive/`, build caches, symbolic links, unpinned dependencies, or
  production subscriber credentials.
- **Safe installer contract**: Installers leave systemd units disabled at boot
  by default and never mutate the peer platform's stack or database.

## Pre-Release Checklist

1. Synchronize version strings across root `VERSION`, backend `__version__`,
   frontend package manifests, `README.md` / `README.zh-CN.md` badges,
   `docs/releasing*.md`, and `CHANGELOG.md` (enforced by `make version-audit`).
2. Verify Python requirement locks, npm lockfiles, pinned upstream commits, and
   container image digests.
3. Run `make ci` to verify backend test suites, production frontend builds, and
   repository audits.
4. Execute the manual `Extended checks` workflow against the release candidate,
   covering Jetson Python 3.10, Spark Python 3.12, and both browser end-to-end
   suites. Resolve any failures before tagging.

## Build Offline ARM64 Archives

Complete the development environment bootstrap first. Builds run on macOS or
Linux hosts with Python `3.10–3.12` and Node.js `22`, targeting a fresh output
directory. Each build compiles the corresponding frontend bundle and downloads
pinned Linux ARM64 wheels for the target host runtime (`CPython 3.10 / Ubuntu
22.04` for Jetson; `CPython 3.12 / Ubuntu 24.04` for Spark). Environment markers
are evaluated against the target runtime, ensuring Jetson bundles include
`exceptiongroup` even when built on newer Python hosts.

```sh
make build-jetson-release RELEASE_OUT=/tmp/agentic-ocudu-jetson
make build-spark-release RELEASE_OUT=/tmp/agentic-ocudu-spark
```

Produced release bundles are named
`agentic-ocudu-jetson-<version>-linux-arm64.tar.gz` and
`agentic-ocudu-spark-<version>-linux-arm64.tar.gz`.

Each output directory contains `stage/`, the `.tar.gz` archive, and its
`.tar.gz.sha256` digest; Jetson builds also retain downloaded `wheels/` outside
`stage/`. The manifest records source revision, workspace cleanliness, target
architecture, and Python version—builds from a dirty working tree are
development candidates rather than clean releases. Packaging scripts validate
wheel tags, Python markers, lockfile membership, and transitive closure before
archiving, and checksum verifiers reject tampered, extra, or unsafe paths. Keep
generated archives outside Git.

Shell build wrappers accept the same `--output <new-directory>` flag with
`PYTHON` pointed at your development interpreter. Low-level staging scripts are
internal helpers and do not produce final archives.

## Deploy and Verify

Transfer the archive, validate its SHA-256 checksum, unpack it into a clean
staging directory, and run `verify` and `preflight`/`check-host` prior to
installation. Installation must preserve boot-disabled defaults and leave the
peer platform and protocol stack untouched. After starting services, validate
`/api/v1/health`, authentication, SSE streams, and the platform's primary
workflow.

Run `python3 deploy/manage.py verify` and `python3 deploy/manage.py preflight`
inside an unpacked Jetson package, or `python3 install.py verify --path .` and
`python3 install.py check-host --path .` inside Spark, using the host's
required Python version. Automated preflight checks supplement—and never replace—
the target-host install/rollback hardware acceptance gate.

## Rollback Evidence

Prior to upgrading, record the active version, SQLite schema revision, and
backup path. Execute one complete rollback to the previous release, verify
service health, and then re-install the release candidate. Archive a sanitized
acceptance record containing date, source commit, version, manifest checksum,
target architecture, executed commands, observed results, rollback identifier,
and any unverified scope.
