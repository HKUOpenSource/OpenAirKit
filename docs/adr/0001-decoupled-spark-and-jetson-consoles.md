# ADR-0001: Keep Spark Console and Jetson Console Decoupled with Unified Version Governance

[简体中文](0001-decoupled-spark-and-jetson-consoles.zh-CN.md)

- **Status**: Accepted
- **Date**: 2026-11-24

## Context

OpenAirKit runs two Linux ARM64 management consoles on distinct physical hosts
with different Python runtimes and failure domains:

- **Spark Console** (`apps/spark-console/`) supervises the DGX Spark base
  station, OCUDU gNB, and Open5GS 5GC containers on Python `3.12`.
- **Jetson Console** (`apps/jetson-console/`) supervises the Jetson Orin UE
  host, Quectel RM520N-GL modem AT/USB state, and Wi-Fi/cellular route
  failover on Python `3.10`.

While both consoles use Astryx Core/Charts/Neutral (`packages/console-ui/`) and
have a similar FastAPI + React layout, merging them into a single configurable
monolith or sharing cross-platform runtime packages (`auth`, SQLite schemas,
React page wrappers) introduces cross-runtime coupling, larger rollback blast
radii, and live-host migration risk. Conversely, allowing console version numbers
and shared dependencies to drift independently causes release confusion and
duplicated security fixes.

## Decision

1. **Keep the two applications decoupled at runtime and source boundaries**:
   `apps/spark-console/` and `apps/jetson-console/` maintain independent
   backends, frontends, SQLite databases, installers, and systemd services.
   `packages/console-ui/` remains restricted to platform-neutral UI setup with
   no business logic.
2. **Unify repository version governance**: Adopt a single canonical version in
   root [`VERSION`](../../VERSION) (starting at `1.0.0`) rather than separate
   per-console version streams.
3. **Prevent silent drift via CI audits**: Enforce version synchronization and
   shared Python/npm dependency pin parity across both consoles via
   [`scripts/audit/version_audit.py`](../../scripts/audit/version_audit.py) in
   `make check` and `make ci`.

## Consequences

- Security patches, UI tokens, and browser timestamp behavior stay aligned across
  both consoles without creating fragile runtime abstractions or breaking
  existing `/etc` and `/var/lib` live-host state.
- Contributors must bump [`VERSION`](../../VERSION) and synchronize both
  console manifests together, enforced automatically by CI.
- See [Architecture](../architecture.md) for the three-plane system overview.
