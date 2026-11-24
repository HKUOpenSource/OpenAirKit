# ADR-0001: 保持 Spark Console 与 Jetson Console 解耦并实施统一版本号治理

[English](0001-decoupled-spark-and-jetson-consoles.md)

- **状态**：已采纳
- **日期**：2026-11-24

## 背景

OpenAirKit 的两套控制台部署在硬件职责与 Python 运行时均不同的 ARM64 设备上：

- **Spark Console**（`apps/spark-console/`）运行于 DGX Spark（Python `3.12`），负责基站主机观测、OCUDU gNB 与 Open5GS 核心网受限控制。
- **Jetson Console**（`apps/jetson-console/`）运行于 Jetson Orin（Python `3.10`），负责 5G 模组 AT/USB 状态监管与 Wi-Fi/蜂窝路由故障切换。

两者虽然同样使用 Astryx Core/Charts/Neutral（`packages/console-ui/`）与 FastAPI + React 栈，但如果强行合并为单个“按角色参数切换”的应用或抽取共享鉴权/业务组件，会引入 Python 3.10/3.12 跨版本耦合、扩大现场升级回滚面，并容易破坏现网密码哈希与 SQLite Schema 兼容性。另一方面，如果长期放任两端使用各自独立递增的版本号与依赖版本，又会带来维护认知分裂和漏修风险。

## 决策

1. **保持运行时与源码边界严格解耦**：`apps/spark-console/` 与 `apps/jetson-console/` 维持各自独立的后端、前端、本地数据库、安装脚本与 systemd 单元；`packages/console-ui/` 仅承担平台无关的 UI 基础封装，不引入业务逻辑。
2. **实行仓库级统一版本号治理**：以根目录 [`VERSION`](../../VERSION) 为唯一版本源（自 `1.0.0` 起），取代两端分裂的独立版本号。
3. **以自动化审计防止配置漂移**：通过 [`scripts/audit/version_audit.py`](../../scripts/audit/version_audit.py) 在 `make check` 与 `make ci` 中自动校验两端版本号与共享 Python/npm 依赖锁定版本的一致性。

## 影响

- 既能避免不必要的跨平台耦合与过度抽象、保障现网主机零迁移风险升级，又能防止共享依赖与安全策略出现漂移。
- 每次发版需同步维护统一版本，已通过仓库 CI 门禁自动兜底。详见[系统架构](../architecture.zh-CN.md)。
