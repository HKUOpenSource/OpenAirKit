# ADR-0003: 强制控制台回环隔离、预留端网侧 AI 推理端口并锁定开机自连哈希

[English](0003-loopback-isolation-and-ai-port-reservation.md)

- **状态**：已采纳
- **日期**：2026-11-24

## 背景

OpenAirKit 的两端控制台直接管理模组恢复、路由切换与基站/核心网启停操作，同时 DGX Spark 与 Jetson Orin 又承担本地 AI 推理与端网协同服务。若控制台监听通配网卡或与推理服务争用端口，或者无人值守冷重启协调器在配置/版本变化后盲目执行恢复操作，都会带来安全暴露面或现场失联风险。

## 决策

1. **控制台仅绑定回环接口 `127.0.0.1`**：Spark Console 固定监听 `127.0.0.1:8877`，Jetson Console 固定监听 `127.0.0.1:8878`，并启用 `TrustedHostMiddleware`、`X-Frame-Options: DENY`、严格 CSP、CSRF 校验、Origin 校验与请求体大小上限；远程运维统一经由 SSH 本地端口转发访问。
2. **为共址 AI 服务保留 `127.0.0.1:8000–8002` 端口段**：将 OCUDU 本地 JSON 遥测回环端口与防火墙守护固定在 `127.0.0.1:8879`，确保常见本地推理与模型服务端口不被协议栈占用。
3. **启用可选开机自连时锁定配置与版本哈希**：当主机开启 [`deploy/jetson/boot_connect.py`](../../deploy/jetson/boot_connect.py) 后，`/etc/aoc-v2-jetson/boot.json` 会记录 `device.json` 与 `manifest.json` 的 SHA-256 摘要，防止版本或配置未经确认即自动执行冷重启入网编排。

## 影响

- 端网侧二次开发的 AI 流水线可直接使用 `127.0.0.1:8000–8002` 并按需对接控制台 REST/SSE 接口，无端口冲突。
- 已开启开机自连的 Jetson 主机在升级新版本后须同步刷新 `/etc/aoc-v2-jetson/boot.json` 中的哈希值（详见[Jetson 故障排查](../troubleshooting-ue-jetson.zh-CN.md)与[Jetson 安装指南](../setup-ue-jetson.zh-CN.md)）。完整端口规划见[端口与运行时参考](../reference/ports-and-runtime.zh-CN.md)与[端网侧 AI 扩展指南](../ai-customization.zh-CN.md)。
