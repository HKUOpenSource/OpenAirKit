# 架构决策记录（ADRs）

[English](README.md)

本目录记录 **OpenAirKit** 在系统设计、模块边界、离线发布与运行时隔离方面的关键架构决策，帮助后续贡献者理解仓库审计规则与演进约束的底层原因。

| 编号 | 决策主题 | 状态 |
| --- | --- | --- |
| [ADR-0001](0001-decoupled-spark-and-jetson-consoles.md) | 保持 Spark Console 与 Jetson Console 解耦并实施统一版本号治理 | 已采纳 |
| [ADR-0002](0002-offline-arm64-wheelhouse-releases.md) | 采用按端侧目标平台隔离的离线 ARM64 Wheelhouse 发布包与默认禁用开机自启策略 | 已采纳 |
| [ADR-0003](0003-loopback-isolation-and-ai-port-reservation.md) | 强制控制台回环隔离、预留端网侧 AI 推理端口并锁定开机自连哈希 | 已采纳 |
