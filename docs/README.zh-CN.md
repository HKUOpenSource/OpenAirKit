# 文档导航

本目录是 Agentic-OCUDU 当前实现的唯一文档事实来源，只描述仍受支持的代码、
发布边界和已经观测到的行为。退役计划与工具保存在本目录之外，不定义当前产品。

## 核心指南

| 目标 | 文档 |
| --- | --- |
| 理解组件、端口与信任边界 | [架构](architecture.zh-CN.md) |
| 安装与初始化 Jetson Console（0.6.2） | [Jetson 安装](setup-ue-jetson.zh-CN.md) |
| 安装 Spark Platform（0.2.1）与 V2 协议栈 | [Spark 安装](setup-bs-spark.zh-CN.md) |
| 查阅 UE 接入、策略与路由语义 | [UE 接入与实验室策略](ue-access-policy.zh-CN.md) |
| 查阅已验证的 TB01 SIM 烧录方法 | [TB01 SIM 烧录](sim-programming-tb01.zh-CN.md) |
| 操作或恢复 Jetson | [Jetson 运维](jetson-operations.zh-CN.md) |
| 操作 RAN、核心网和监测平台 | [Spark 运维](spark-operations.zh-CN.md) |
| 排查 UE 侧故障 | [Jetson 故障排查](troubleshooting-ue-jetson.zh-CN.md) |
| 排查基站侧故障 | [Spark 故障排查](troubleshooting-bs-spark.zh-CN.md) |
| 构建和审计发布 | [发布指南](releasing.zh-CN.md) |
| 配置受限免密维护助手 | [维护助手指南](../deploy/maintenance/README.zh-CN.md) |
| 使用仓库代码图 | [CodeGraph 指南](coding-agent-codegraph.zh-CN.md) |
| 查看交付状态 | [路线图](roadmap.md) |

## 近期里程碑与验收记录

| 主题 | 记录 |
| --- | --- |
| 验收规范与早期归档索引 | [验收记录](acceptance/README.md) |
| Spark 0.2.1 与 Jetson 0.6.2 实机对齐（`8879`、ECM、`boot_connect`） | [2026-11-23 对齐验收](acceptance/2026-11-23-spark-ue-alignment.zh-CN.md) |
| Jetson RM520N RNDIS AT 接口发现 | [2026-10-16 RNDIS 发现](acceptance/2026-10-16-jetson-rndis-at.zh-CN.md) |
| Jetson 蜂窝/Wi-Fi 自动切换验收 | [2026-10-16 切换验收](acceptance/2026-10-16-jetson-cellular-failover.zh-CN.md) |
| Jetson 蜂窝性能观测 | [2026-10-16 性能观测](acceptance/2026-10-16-jetson-cellular-performance.zh-CN.md) |
| 多设备 0.6.1 / 0.2.1 部署与回滚 | [2026-09-28 部署记录](acceptance/2026-09-28-review-deployment.zh-CN.md) |
| 0.6.2 蜂窝恢复自动切回修复 | [2026-09-28 路由修复](acceptance/2026-09-28-cellular-failback.zh-CN.md) |

命令和界面名称以英文文档为准，`.zh-CN.md` 文件提供对应的简体中文说明。
