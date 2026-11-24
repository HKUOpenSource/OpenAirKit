# UE 接入与实验室策略

[English](ue-access-policy.md)

本项目仅支持 OCUDU + Open5GS。标准网络接入不需要 UE 知道 Spark 管理地址、
gNB 实现或固定 PCI。实验室仍需对齐 SIM 订阅、PLMN、DNN、切片与支持的 PDU 类型。
本应用目前仅验证 IPv4；配置中的切片和 QoS 是预期值，不代表模组已协商成功。

Jetson schema 3 将配置拆为 `network`（接入与 PDU 预期）、`selection`（观察到的
NR SA、频段、可选 PCI、可选 **SSB** ARFCN）、`diagnostics`（绑定探测地址和必需
探测项）、`management`（Wi-Fi 回退与 Tailscale 路由检查）及 `recovery`（有界恢复策略）。
逐字段校验。修改预期值不会自动修改 Open5GS，也不会隐式下发模组配置。
Device Setup 检查并保留现有无线设置。

`selection.mode` 为 `observe_only`，只报告策略匹配，不下发锁频或锁小区命令。
此类写入需要经过确认的模组能力与完整前后回读，目前不支持。`radio_reference`
中的载波中心 ARFCN 不是服务 SSB ARFCN。schema 2 迁移保留原频段、PCI 观察策略
和无线参考参数；运维人员审核实验室策略后可将 PCI、SSB ARFCN 设为 null。
状态观察或频率约束都不能消除物理射频干扰。

Overview 独立显示注册、PDU、数据验证、实验室策略和管理保护。数据验证要求新鲜
SIM、接入 PLMN 上的 NR SA、注册、预期池内的有效 IPv4 PDU、RNDIS 地址及多个
配置的绑定探测。注册、服务小区、PDU 或接口变化会使旧探测失效；过期证据不能
继续宣称已连接。诊断失败不会清除注册状态，管理保护失败会阻止写入但不改变注册。

成功完成配置或恢复后启用自动恢复。注册/PDU 丢失先等待自然恢复，默认 120 秒；
随后最多运行两次恢复任务，间隔至少 300 秒。每任务最多重连一次，重置冷却跨进程
重启保留。取消、维护会暂停自动恢复；仅诊断失败不会重置。数据持续健康达到冷却
时长后才重置尝试预算。

IPv4 默认路由切换独立于自动模组恢复权限。连续两组新鲜探测（含公网）成功后优先
蜂窝，失败或证据过期时回退 Wi-Fi。详见[路由行为与限制](jetson-operations.zh-CN.md#恢复与连通性)。

ext-DN 在核心网内部的 8080 端口提供固定小响应 `/health`，不映射主机端口，
不运行测速服务器。历史测速证据继续保留为历史，不再作为发布门槛。
