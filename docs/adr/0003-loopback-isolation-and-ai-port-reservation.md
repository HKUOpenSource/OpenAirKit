# ADR-0003: Enforce Loopback-Only Console Binding, Reserved AI Inference Ports, and Boot Hash Pinning

[简体中文](0003-loopback-isolation-and-ai-port-reservation.zh-CN.md)

- **Status**: Accepted
- **Date**: 2026-11-24

## Context

Both consoles expose authenticated operational endpoints (including route
failover, modem recovery, and stack control) on AI-capable edge hardware where
administrators also deploy co-located inference and telemetry pipelines over
loopback ports. Exposing console listeners on wildcard interfaces or allowing
unverified upgrades alongside unattended cold-boot attachment poses security and
operational hazards.

## Decision

1. **Bind console listeners strictly to `127.0.0.1`**: Spark Console binds
   `127.0.0.1:8877` and Jetson Console binds `127.0.0.1:8878`, both paired with
   `TrustedHostMiddleware`, strict CSP/frame headers (`X-Frame-Options: DENY`),
   CSRF tokens, origin validation, and bounded request payload limits. Remote
   access uses SSH local port forwarding rather than public interface exposure.
2. **Reserve `127.0.0.1:8000–8002` for co-located AI services**: OCUDU loopback
   JSON metrics and the firewall guard were placed on `127.0.0.1:8879` so the
   standard inference port range `8000–8002` remains unobstructed at both the
   RAN/core host and UE host.
3. **Pin cold-boot state hashes when opt-in boot coordination is enabled**:
   When an administrator enables [`deploy/jetson/boot_connect.py`](../../deploy/jetson/boot_connect.py),
   `/etc/aoc-v2-jetson/boot.json` pins SHA-256 digests of `device.json` and the
   installed `manifest.json` so silent config or release drift halts unattended
   modem attachment until explicitly refreshed after upgrade.

## Consequences

- Co-located AI workloads can bind `127.0.0.1:8000–8002` and query console
  REST/SSE endpoints without port contention.
- Remote browser users access consoles over authenticated SSH tunnels with host
  validation intact.
- Upgrading a Jetson host with boot coordination active requires refreshing
  `/etc/aoc-v2-jetson/boot.json` digests (documented in
  [Jetson Troubleshooting](../troubleshooting-ue-jetson.md) and
  [Jetson Setup](../setup-ue-jetson.md)). See
  [AI Extensibility Guide](../ai-customization.md) and
  [Ports & Runtime](../reference/ports-and-runtime.md) for port allocations.
