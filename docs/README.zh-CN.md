# 文档导航

[English](README.md)

本目录按照 **架构概览 → 部署与运维指南 → 技术参考与附录**
三层结构组织全库文档；所有参数契约、接口规范与硬件附录均统一收口于 `docs/reference/`。

## 架构概览

| 查阅目标 | 文档 |
| --- | --- |
| 理解三平面架构、组件归属、隔离边界与证据语义 | [系统架构](architecture.zh-CN.md) |
| 了解控制台解耦、离线发布与 AI 端口隔离等核心架构权衡 | [架构决策记录（ADR）](adr/README.zh-CN.md) |
| 查看完整硬件清单（BOM）、物理拓扑与主机前置条件 | [硬件清单与拓扑](hardware-and-topology.zh-CN.md) |

## 部署、运维与 AI 扩展指南

| 查阅目标 | 文档 |
| --- | --- |
| 按跨主机全链路流程完成系统部署与联调 | [端到端快速搭建指南](quickstart.zh-CN.md) |
| 安装 Spark Console 与基站协议栈 | [Spark 安装指南](setup-bs-spark.zh-CN.md) |
| 编译并部署独立的 OCUDU + Open5GS 协议栈发布包 | [Spark 协议栈部署](../deploy/spark/stack/README.zh-CN.md) |
| 构建并核验 Open5GS ARM64 运行镜像 | [Open5GS ARM64 构建](../stacks/open5gs/build/README.md) |
| 创建 Open5GS 订阅并烧录 5G USIM 卡 | [Open5GS 开户与 USIM 烧录指南](sim-provisioning.zh-CN.md) |
| 安装、初始化并配置 Jetson Console 开机自连 | [Jetson Console 安装指南](setup-ue-jetson.zh-CN.md) |
| 使用 Spark Web 控制台并执行全栈生命周期管理 | [Spark Console 运维指南](spark-operations.zh-CN.md) |
| 使用 Jetson Web 控制台、双路径路由与有界自愈 | [Jetson Console 运维指南](jetson-operations.zh-CN.md) |
| 配置可选受限免密维护助手（`aoc-maintain`） | [维护助手指南](../deploy/maintenance/README.zh-CN.md) |
| 基于端网预留算力与接口开发自定义 AI 服务与流水线 | [端网侧 AI 扩展指南](ai-customization.zh-CN.md) |
| 排查基站侧与核心网异常 | [Spark 故障排查](troubleshooting-bs-spark.zh-CN.md) |
| 排查 UE 侧、模组或路由异常 | [Jetson 故障排查](troubleshooting-ue-jetson.zh-CN.md) |

## 技术参考与附录

| 专题 | 参考文档 |
| --- | --- |
| 射频基线（`n78`）、Open5GS 数据契约与 UE 接入策略语义 | [网络契约与射频基线](reference/network-and-rf-profile.zh-CN.md) |
| 回环端口分配、低时延保护、路由阈值、恢复预算与退出码 | [端口与运行时参考](reference/ports-and-runtime.zh-CN.md) |
| Spark Console 与 Jetson Console 全量 REST / SSE 接口规范 | [REST 与 SSE 接口参考](reference/api-reference.zh-CN.md) |
| RM520N-GL USB 布局、QMAP 核查、内核兼容性与 TB01 APDU 附录 | [硬件与 TB01 附录](reference/hardware-notes.zh-CN.md) |
| 5G SA 与平台核心术语定义 | [核心术语表](reference/glossary.zh-CN.md) |

## 发布维护、视觉素材与实机基线

| 查阅目标 | 文档 |
| --- | --- |
| 搭建本地开发环境、运行模拟预览、浏览器 E2E 与全套审计 | [开发者指南](development.zh-CN.md) |
| 构建、校验并打包 ARM64 离线发布包 | [发布指南](releasing.zh-CN.md) |
| 查看视觉素材、图表资产与截图脱敏规范 | [视觉素材规范](assets/README.md) |
| 查看产品能力里程碑 | [产品路线图](roadmap.zh-CN.md) |
| 查阅脱敏后的硬件实机验收基线 | [硬件验收基线索引](acceptance/README.md) |

命令行参数与界面英文标签以英文文档为规范基准，`.zh-CN.md` 提供等价的简体中文工程说明。
