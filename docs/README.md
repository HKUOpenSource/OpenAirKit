# Documentation

This directory is the source of truth for the current Agentic-OCUDU system.
Documents describe only supported code, release boundaries and observed
behavior. Retired plans and tools live outside this directory and do not define
the product.

## Core guides

| Need | Guide |
| --- | --- |
| Understand components, ports and trust boundaries | [Architecture](architecture.md) |
| Install and commission the Jetson Console (0.6.2) | [Jetson setup](setup-ue-jetson.md) |
| Install the Spark Platform (0.2.1) and V2 stack | [Spark setup](setup-bs-spark.md) |
| Review UE access, policy and routing rules | [UE access and lab policy](ue-access-policy.md) |
| Review the validated TB01 SIM programming method | [TB01 SIM programming](sim-programming-tb01.md) |
| Operate or recover the Jetson side | [Jetson operations](jetson-operations.md) |
| Operate the RAN, core and monitor | [Spark operations](spark-operations.md) |
| Diagnose a UE-side fault | [Jetson troubleshooting](troubleshooting-ue-jetson.md) |
| Diagnose a base-station-side fault | [Spark troubleshooting](troubleshooting-bs-spark.md) |
| Build and audit a release | [Releasing](releasing.md) |
| Configure passwordless restricted maintenance | [Maintenance helper](../deploy/maintenance/README.md) |
| Use the repository graph | [CodeGraph guide](coding-agent-codegraph.md) |
| Check delivery status | [Roadmap](roadmap.md) |

## Recent milestones & acceptance records

| Focus | Record |
| --- | --- |
| Full acceptance rules & older records | [Acceptance index](acceptance/README.md) |
| Spark 0.2.1 + Jetson 0.6.2 runtime alignment (`8879`, ECM, `boot_connect`) | [2026-11-23 alignment](acceptance/2026-11-23-spark-ue-alignment.md) |
| Jetson RM520N RNDIS AT interface discovery | [2026-10-16 RNDIS discovery](acceptance/2026-10-16-jetson-rndis-at.md) |
| Jetson cellular/Wi-Fi failover acceptance | [2026-10-16 cellular failover](acceptance/2026-10-16-jetson-cellular-failover.md) |
| Jetson cellular performance observations | [2026-10-16 cellular performance](acceptance/2026-10-16-jetson-cellular-performance.md) |
| Multi-device 0.6.1 / 0.2.1 deployment & rollback | [2026-09-28 review deployment](acceptance/2026-09-28-review-deployment.md) |
| 0.6.2 automatic cellular failback repair | [2026-09-28 cellular failback](acceptance/2026-09-28-cellular-failback.md) |

English is the normative documentation language for commands and interface
names. The matching `.zh-CN.md` files provide Simplified Chinese guidance.
