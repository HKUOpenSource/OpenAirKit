# Releasing

[简体中文](releasing.zh-CN.md)

Jetson Console and Spark Platform use independent versions, source trees, and
release artifacts (`0.6.2` and `0.2.1` respectively). Release one platform at a
time.

## Release boundary policy

Every generated archive is verified against the following repository boundaries:

- **Single-platform isolation**: Each package contains only its own
  application, deployment tools, locked dependencies, wheelhouse, version,
  manifest, and third-party license notices.
- **Excluded artifacts**: Release audits reject files from the other platform,
  `archive/`, generated caches or outputs, symlinks, mutable/unpinned
  dependencies, and production subscriber data or credentials.
- **Safe installer behavior**: Installers never enable boot startup
  automatically and never modify the other platform's stack or database.

## Before building

1. Update the backend `__version__`, frontend package files, `CHANGELOG.md` and
   `RELEASE-VERSION` source together.
2. Confirm Python locks, npm lockfiles, upstream revisions and image digests.
3. Run `make ci` for backend tests, production frontend builds and repository audits.
4. Run the manual `Extended checks` workflow on the release candidate, covering
   Jetson Python 3.10, Spark Python 3.12 and both browser suites. These checks are
   not part of the minimal automatic PR gate. Resolve failures before release;
   moving a test to manual execution does not make a failure acceptable.

## Build

Run the development bootstrap first. Builders can run on macOS or Linux with
Python 3.10–3.12 and Node.js 22; each output directory must be new. They build
the selected frontend and download exactly pinned Linux ARM64 wheels for
Jetson CPython 3.10 / Ubuntu 22.04 or Spark CPython 3.12 / Ubuntu 24.04.
Dependency markers are evaluated for that target, including Jetson's
`exceptiongroup` dependency when building on a newer Python.

```sh
make build-jetson-release RELEASE_OUT=/tmp/agentic-ocudu-jetson
make build-spark-release RELEASE_OUT=/tmp/agentic-ocudu-spark
```

The expected artifacts are
`agentic-ocudu-jetson-<version>-linux-arm64.tar.gz` and
`agentic-ocudu-spark-<version>-linux-arm64.tar.gz`. A package contains only its
application, deployment tools, locked dependencies, wheelhouse, version,
manifest and third-party license material.

The output directory contains `stage/`, the archive and a matching
`.tar.gz.sha256`. Jetson also retains the downloaded `wheels/` outside the
stage. Each manifest records source commit, dirty status, architecture and
Python target; an uncommitted build is a development candidate, not a clean
release. Builders validate wheel tags, Python requirements, exact lock
membership and transitive dependencies before archiving. Packages are staged
from explicit application/deployment inputs, excluding the other platform
and archived material; checksum verifiers reject changed or additional files
and unsafe paths. Keep generated packages outside version control.

The shell build entry points accept the same `--output <new-directory>`
option. Set their `PYTHON` environment variable to the development interpreter.
Low-level staging scripts are implementation tools and do not create archives.

## Deploy and verify

Transfer the archive, verify its checksum, unpack into a new staging directory,
and run the included preflight and verify actions before install. Installation
must not enable services at boot or change the other application or protocol
stack. After start, check health, login, SSE and the platform-specific critical
workflow.

Inside the unpacked Jetson package, run `python3 deploy/manage.py verify` and
`python3 deploy/manage.py preflight`; inside Spark run
`python3 install.py verify --path .` and `python3 install.py check-host --path .`.
Run target-side checks with the platform's required Python version. These
checks do not replace the separate installation/rollback hardware gate.

## Rollback evidence

Before upgrade, record the active release, database schema and backup path.
Perform one rollback to the previous release, verify health, then reinstall the
candidate. Add a redacted acceptance record containing date, source revision,
version, manifest checksum, target architecture, commands, results, rollback
identifier and unverified items.
