# 文档导航

[English](README.md)

本目录按 **概览与架构（`L1`）→ 主干操作指南（`L2`）→ 技术参考与附录（`L3`）**
三层渐进式结构组织，所有参数、接口与硬件附录均集中收口于 `docs/reference/`。

## 概览与架构（`L1`）

| 目标 | 文档 |
| --- | --- |
| 理解三平面架构、组件归属、隔离边界与证据语义 | [系统架构](architecture.zh-CN.md) |
| 查看硬件清单（含 Waveshare M.2 载板）、物理接线与系统前置条件 | [硬件清单与拓扑](hardware-and-topology.zh-CN.md) |

## 搭建、运维与定制指南（`L2`）

| 目标 | 文档 |
| --- | --- |
| 按 0→1 主线完成跨主机搭建与联调 | [端到端快速搭建指南](quickstart.zh-CN.md) |
| 安装 Spark Platform 与基站协议栈 | [Spark 安装指南](setup-bs-spark.zh-CN.md) |
| 构建并部署独立的 OCUDU + Open5GS 协议栈包 | [Spark 协议栈部署](../deploy/spark/stack/README.zh-CN.md) |
| 构建并核验 Open5GS ARM64 运行镜像 | [Open5GS ARM64 构建](../stacks/open5gs/build/README.md) |
| 添加 Open5GS 订阅并烧录 5G USIM 卡 | [Open5GS 开户与 USIM 配卡](sim-provisioning.zh-CN.md) |
| 安装、初始化并配置 Jetson Console 开机自连 | [Jetson Console 安装指南](setup-ue-jetson.zh-CN.md) |
| 使用 Spark Web 控制台与整套启停运维 | [Spark Platform 运维指南](spark-operations.zh-CN.md) |
| 使用 Jetson Web 控制台、双路径路由与自愈功能 | [Jetson Console 运维指南](jetson-operations.zh-CN.md) |
| 配置可选受限免密维护助手（`aoc-maintain`） | [维护助手指南](../deploy/maintenance/README.zh-CN.md) |
| 基于双端预留算力与接口开展 DIY AI 定制 | [双端 AI 定制指南](ai-customization.zh-CN.md) |
| 排查基站侧与核心网问题 | [Spark 故障排查](troubleshooting-bs-spark.zh-CN.md) |
| 排查 UE 侧、模组或路由问题 | [Jetson 故障排查](troubleshooting-ue-jetson.zh-CN.md) |

## 技术参考与附录（`L3`）

| 专题 | 参考文档 |
| --- | --- |
| 射频基线（`n78`）、Open5GS 数据契约与 UE 接入策略语义 | [网络契约与射频基线](reference/network-and-rf-profile.zh-CN.md) |
| 回环端口分配、低时延保护、路由阈值、恢复预算与退出码 | [端口与运行时参考](reference/ports-and-runtime.zh-CN.md) |
| Spark Platform 与 Jetson Console 全量 REST / SSE 接口规范 | [REST 与 SSE 接口参考](reference/api-reference.zh-CN.md) |
| RM520N-GL USB 布局、QMAP 核查、内核兼容性与 TB01 APDU 附录 | [硬件与 TB01 附录](reference/hardware-notes.zh-CN.md) |
| 5G SA 与平台核心术语定义 | [核心术语表](reference/glossary.zh-CN.md) |

## 维护、品牌素材与实机基线

| 目标 | 文档 |
| --- | --- |
| 构建、校验并打包 ARM64 离线发布 | [发布指南](releasing.zh-CN.md) |
| 查看品牌解耦矩阵、Logo 占位、硬件实拍与脱敏规范 | [视觉素材与品牌替换规范](assets/README.md) |
| 查看产品能力里程碑 | [产品路线图](roadmap.zh-CN.md) |
| 查阅脱敏后的硬件实机验收基线 | [硬件验收基线索引](acceptance/README.md) |

命令与界面名称以英文文档为准，`.zh-CN.md` 文件提供对应的简体中文说明。
