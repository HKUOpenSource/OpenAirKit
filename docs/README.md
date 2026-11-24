# Documentation

[简体中文](README.zh-CN.md)

This directory is the source of truth for the current **Agentic-OCUDU** system.
Documents describe only supported code, hardware contracts, release boundaries
and observed behavior. Retired plans and tools live outside this directory and
do not define the product.

## 1. Architecture & Hardware Prerequisites

| Need | Guide |
| --- | --- |
| Check hardware BOM, Jetson M.2 carrier, wiring, ports and OS prerequisites | [Hardware & Topology](hardware-and-topology.md) |
| Understand components, planes, ports and trust boundaries | [Architecture](architecture.md) |
| Review UE access, PLMN/slice/DNN and routing rules | [UE Access and Lab Policy](ue-access-policy.md) |

## 2. End-to-End Setup & Bring-Up

| Need | Guide |
| --- | --- |
| Follow the 0-to-1 end-to-end bring-up path | [End-to-End Quickstart](quickstart.md) |
| Install Spark Platform (`0.2.1`) and base-station runtime | [Spark Setup](setup-bs-spark.md) |
| Build and deploy the independent OCUDU + Open5GS stack | [Spark Stack Deployment](../deploy/spark/stack/README.md) |
| Install, commission and configure boot auto-connect on Jetson Console (`0.6.2`) | [Jetson Setup](setup-ue-jetson.md) |
| Provision an Open5GS subscriber and program TB01 USIM cards | [TB01 SIM Programming](sim-programming-tb01.md) |

## 3. Platform Management & Operations

| Need | Guide |
| --- | --- |
| Use Spark Web Console, REST/SSE APIs and stack lifecycle scripts | [Spark Operations](spark-operations.md) |
| Use Jetson Web Console, REST/SSE APIs and routing/recovery controls | [Jetson Operations](jetson-operations.md) |
| Configure passwordless restricted maintenance (`aoc-maintain`) | [Maintenance Helper](../deploy/maintenance/README.md) |
| Diagnose base-station or core faults | [Spark Troubleshooting](troubleshooting-bs-spark.md) |
| Diagnose UE, modem or routing faults | [Jetson Troubleshooting](troubleshooting-ue-jetson.md) |

## 4. DIY AI Customization & Extension

| Need | Guide |
| --- | --- |
| Build custom AI modules using reserved Spark/Jetson headroom and REST/SSE APIs | [DIY AI Customization](ai-customization.md) |

## 5. Maintainer, Release & Verification Records

| Need | Document |
| --- | --- |
| Build, package and audit offline ARM64 releases | [Releasing](releasing.md) |
| Use the repository code graph for development | [CodeGraph Guide](coding-agent-codegraph.md) |
| Check current engineering delivery milestones | [Roadmap](roadmap.md) |
| Review acceptance rules and historical hardware verification logs | [Acceptance Index](acceptance/README.md) |
| Latest Spark `0.2.1` + Jetson `0.6.2` multi-UE hardware alignment record | [2026-11-23 Alignment Record](acceptance/2026-11-23-spark-ue-alignment.md) |

English is the normative documentation language for commands and interface
names. The matching `.zh-CN.md` files provide Simplified Chinese guidance.
