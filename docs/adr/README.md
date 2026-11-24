# Architecture Decision Records (ADRs)

[简体中文](README.zh-CN.md)

This directory records key architectural decisions behind **OpenAirKit** so
contributors understand why module boundaries, release packaging, and runtime
isolation constraints are enforced the way they are.

| ID | Title | Status |
| --- | --- | --- |
| [ADR-0001](0001-decoupled-spark-and-jetson-consoles.md) | Keep Spark Console and Jetson Console Decoupled with Unified Version Governance | Accepted |
| [ADR-0002](0002-offline-arm64-wheelhouse-releases.md) | Package Target-Specific Offline ARM64 Wheelhouse Releases with Boot-Disabled Defaults | Accepted |
| [ADR-0003](0003-loopback-isolation-and-ai-port-reservation.md) | Enforce Loopback-Only Console Binding, Reserved AI Inference Ports, and Boot Hash Pinning | Accepted |
