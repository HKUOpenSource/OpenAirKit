# Documentation

[简体中文](README.zh-CN.md)

This directory is the source of truth for the current system. Documents describe
only supported code, hardware contracts, release boundaries and observed
behavior. Retired plans and tools live under `archive/` and do not define the
product.

## 1. Architecture & Hardware Prerequisites

| Need | Guide |
| --- | --- |
| Check hardware BOM, Jetson M.2 carrier, wiring, ports and OS prerequisites | [Hardware & Topology](hardware-and-topology.md) |
| Understand three-plane architecture, ownership, ports and glossary | [Architecture](architecture.md) |
| Review UE access, PLMN/slice/DNN and routing rules | [UE Access and Lab Policy](ue-access-policy.md) |

## 2. End-to-End Setup & Bring-Up

| Need | Guide |
| --- | --- |
| Follow the 0-to-1 end-to-end bring-up path | [End-to-End Quickstart](quickstart.md) |
| Install Spark Platform (`0.2.1`) and base-station runtime | [Spark Setup](setup-bs-spark.md) |
| Build and deploy the independent OCUDU + Open5GS stack | [Spark Stack Deployment](../deploy/spark/stack/README.md) |
| Build and verify Open5GS ARM64 images | [Open5GS ARM64 Build](../stacks/open5gs/build/README.md) |
| Install, commission and configure boot auto-connect on Jetson Console (`0.6.2`) | [Jetson Setup](setup-ue-jetson.md) |
| Provision an Open5GS subscriber and program 5G USIM cards (incl. TB01) | [SIM Provisioning & TB01 Reference](sim-programming-tb01.md) |

## 3. Platform Management & Operations

| Need | Guide |
| --- | --- |
| Use Spark Web Console, REST/SSE APIs and stack lifecycle scripts | [Spark Operations](spark-operations.md) |
| Use Jetson Web Console, REST/SSE APIs and routing/recovery controls | [Jetson Operations](jetson-operations.md) |
| Configure optional passwordless restricted maintenance (`aoc-maintain`) | [Maintenance Helper](../deploy/maintenance/README.md) |
| Diagnose base-station or core faults | [Spark Troubleshooting](troubleshooting-bs-spark.md) |
| Diagnose UE, modem or routing faults | [Jetson Troubleshooting](troubleshooting-ue-jetson.md) |

## 4. DIY AI Customization & Extension

| Need | Guide |
| --- | --- |
| Build custom AI modules using reserved Spark/Jetson headroom and REST/SSE APIs | [DIY AI Customization](ai-customization.md) |

## 5. Maintainer, Assets & Verification Baselines

| Need | Document |
| --- | --- |
| Build, package and audit offline ARM64 releases | [Releasing](releasing.md) |
| Replace brand names, Logos, hardware photos and redacted UI screenshots | [Visual Assets & Brand Guide](assets/README.md) |
| Check current product milestones and scope invariants | [Product Roadmap](roadmap.md) |
| Review verified hardware acceptance baselines and redaction rules | [Verified Hardware Baselines](acceptance/README.md) |

English is the normative documentation language for commands and interface
names. The matching `.zh-CN.md` files provide Simplified Chinese guidance.
