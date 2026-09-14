# Releasing

Jetson Console and Spark Platform use independent versions and release
artifacts. Release one platform at a time.

## Before building

1. Update the backend `__version__`, frontend package files, `CHANGELOG.md` and
   `RELEASE-VERSION` source together.
2. Confirm Python locks, npm lockfiles, upstream revisions and image digests.
3. Run `make check` and the selected frontend production build.
4. Run `make docs-audit`, `make release-audit` and `make license-audit`.

## Build

```sh
make build-jetson-release RELEASE_OUT=/tmp/agentic-ocudu-jetson
make build-spark-release RELEASE_OUT=/tmp/agentic-ocudu-spark
```

The expected artifacts are
`agentic-ocudu-jetson-<version>-linux-arm64.tar.gz` and
`agentic-ocudu-spark-<version>-linux-arm64.tar.gz`. A package contains only its
application, deployment tools, locked dependencies, wheelhouse, version,
manifest and third-party license material.

The verifier rejects the other application, `archive/`, development output,
caches, logs, diagnostics, production configuration, symlinks and unlocked
dependencies.

## Deploy and verify

Transfer the archive, verify its checksum, unpack into a new staging directory,
and run the included preflight and verify actions before install. Installation
must not enable services at boot or change the other application or protocol
stack. After start, check health, login, SSE and the platform-specific critical
workflow.

## Rollback evidence

Before upgrade, record the active release, database schema and backup path.
Perform one rollback to the previous release, verify health, then reinstall the
candidate. Add a redacted acceptance record containing date, source revision,
version, manifest checksum, target architecture, commands, results, rollback
identifier and unverified items.
