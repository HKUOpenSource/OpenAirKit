# ADR-0002: Package Target-Specific Offline ARM64 Wheelhouse Releases with Boot-Disabled Defaults

[简体中文](0002-offline-arm64-wheelhouse-releases.zh-CN.md)

- **Status**: Accepted
- **Date**: 2026-11-24

## Context

Lab testbed hosts (DGX Spark and Jetson Orin) often operate in isolated RF/lab
networks where PyPI or npm access during deployment is undesirable or blocked,
and installing an incorrect architecture wheel or enabling faulty network/radio
services automatically at boot can lock administrators out of remote SSH/Tailnet
management links.

## Decision

1. **Build self-contained offline ARM64 archives**: [`scripts/build_release.py`](../../scripts/build_release.py)
   compiles static frontend assets on the build host and downloads locked
   `aarch64` wheels evaluated explicitly against the target runtime markers
   (`CPython 3.10` for Jetson; `CPython 3.12` for Spark).
2. **Enforce single-platform content-addressed verification**: Releases omit peer
   platform files, symlinks, unpinned dependencies, and subscriber credentials.
   Both installers verify SHA-256 checksums before touching target state and
   preserve database/unit backups for rollback.
3. **Keep services disabled at boot by default**: Neither console nor stack
   unit is enabled via `systemctl enable` during standard installation so an
   unintended reboot returns the host to clean baseline networking unless an
   operator explicitly opts in to cold-boot orchestration.

## Consequences

- Builds can run reproducibly on macOS or Linux developer machines and deploy
  completely offline to lab hosts.
- Target Python compatibility issues (such as `exceptiongroup` markers on Python
  `3.10`) are caught at build time in `release_tools.validate_wheels()`.
- See [Releasing](../releasing.md) for build, verification, and rollback gates.
