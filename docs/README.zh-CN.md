# 文档导航

[English](README.md)

本目录是系统当前实现的唯一文档事实来源，只描述受支持的代码、硬件契约、发布边界和已经观测到的行为。
退役计划与历史工具保存在 `archive/` 目录之外，不定义当前产品。

## 1. 架构与硬件前置条件

| 目标 | 文档 |
| --- | --- |
| 查看硬件清单（含 Jetson M.2 扩展载板）、接线拓扑、端口与系统前置条件 | [硬件清单与拓扑](hardware-and-topology.zh-CN.md) |
| 理解三平面架构、组件归属、端口隔离与术语表 | [系统架构](architecture.zh-CN.md) |
| 查阅 UE 接入、PLMN/切片/DNN 与路由语义 | [UE 接入与实验室策略](ue-access-policy.zh-CN.md) |

## 2. 端到端快速拉起与安装

| 目标 | 文档 |
| --- | --- |
| 按 0→1 主线完成跨主机搭建、开户与联调 | [端到端快速搭建指南](quickstart.zh-CN.md) |
| 安装 Spark Platform（`0.2.1`）与基站运行基线 | [Spark 安装](setup-bs-spark.zh-CN.md) |
| 构建并部署独立的 OCUDU + Open5GS 协议栈 | [Spark 协议栈部署](../deploy/spark/stack/README.zh-CN.md) |
| 构建并验证 Open5GS ARM64 运行镜像 | [Open5GS ARM64 构建](../stacks/open5gs/build/README.md) |
| 安装、初始化并配置 Jetson Console（`0.6.2`）开机自连 | [Jetson 安装](setup-ue-jetson.zh-CN.md) |
| 添加 Open5GS 订阅并烧录 5G USIM 卡（含 TB01 参考规范） | [SIM 开户与 TB01 参考](sim-programming-tb01.zh-CN.md) |

## 3. 平台管控与日常运维

| 目标 | 文档 |
| --- | --- |
| 查看 Spark Web 控制台导览、API 速查与启停运维 | [Spark 运维](spark-operations.zh-CN.md) |
| 查看 Jetson Web 控制台导览、API 速查与双路径/自愈状态机 | [Jetson 运维](jetson-operations.zh-CN.md) |
| 配置可选受限免密维护助手（`aoc-maintain`） | [维护助手指南](../deploy/maintenance/README.zh-CN.md) |
| 排查基站侧与核心网故障 | [Spark 故障排查](troubleshooting-bs-spark.zh-CN.md) |
| 排查 UE 侧、模组或路由故障 | [Jetson 故障排查](troubleshooting-ue-jetson.zh-CN.md) |

## 4. 双端 AI 定制与扩展

| 目标 | 文档 |
| --- | --- |
| 了解双端预留算力、实时性隔离与基于 REST/SSE 的 DIY AI 接入方式 | [双端 AI 定制指南](ai-customization.zh-CN.md) |

## 5. 维护、品牌素材与实机基线

| 目标 | 文档 |
| --- | --- |
| 构建、校验并打包 ARM64 离线发布 | [发布指南](releasing.zh-CN.md) |
| 了解品牌更名解耦、Logo 替换、实拍图与脱敏截图规范 | [视觉素材与品牌替换规范](assets/README.md) |
| 查看产品阶段里程碑与范围约定 | [产品路线图](roadmap.zh-CN.md) |
| 查阅硬件实机验收规范与历史基线档案 | [硬件验收基线索引](acceptance/README.md) |

命令和界面名称以英文文档为准，`.zh-CN.md` 文件提供对应的简体中文说明。
