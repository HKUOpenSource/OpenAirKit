# ADR-0002: 采用按端侧目标平台隔离的离线 ARM64 Wheelhouse 发布包与默认禁用开机自启策略

[English](0002-offline-arm64-wheelhouse-releases.md)

- **状态**：已采纳
- **日期**：2026-11-24

## 背景

5G SA 实验台主机（DGX Spark 与 Jetson Orin）常运行在受控网络或外场环境中，部署期间不应依赖公网 PyPI/npm 源；同时，如果控制台或协议栈在首次安装后默认随开机自启，一旦无线或路由状态异常，极易导致远程管理链路失联。

## 决策

1. **构建自包含离线 ARM64 发布包**：由 [`scripts/build_release.py`](../../scripts/build_release.py) 在构建机完成前端静态编译，并按目标端侧运行时标签（Jetson 为 `CPython 3.10`，Spark 为 `CPython 3.12`）解析下载完整 `aarch64` 离线 wheelhouse。
2. **强制单平台隔离与内容寻址校验**：发布包严格剔除对端平台代码、符号链接、未锁定依赖及用户凭据；安装程序在切换前校验全量 SHA-256 清单，并自动备份数据库与旧版单元以支持一键回滚。
3. **默认保持开机自启禁用**：标准安装仅按需启动当前会话服务，不自动执行 `systemctl enable`，仅在运维人员确认基线稳定后才可按需开启冷重启自连协调器。

## 影响

- 可在 macOS 或 Linux 开发机上可复现地打出一键离线部署包，不依赖现场目标机的外网环境。
- Python `3.10` 与 `3.12` 的条件依赖差异在构建期即由 `release_tools.validate_wheels()` 拦截校验。详见[发布工程指南](../releasing.zh-CN.md)。
