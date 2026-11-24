# 核心术语表

[English](glossary.md)

| 术语 | 定义说明 |
| --- | --- |
| **5G SA（独立组网）** | 5G NR 无线接入网（`OCUDU gNB`）通过 N2/N3 接口直接接入原生 5G 核心网（`Open5GS 5GC`），无需 4G LTE 控制面锚点。 |
| **N2 / N3 / N4 / N6** | 3GPP 5G 核心参考点：gNB-AMF 控制面（`N2`/NGAP）、gNB-UPF 用户面（`N3`/GTP-U）、SMF-UPF 会话控制（`N4`/PFCP）与 UPF-外部数据网接口（`N6`）。 |
| **`ext-DN`** | `aoc-v2-open5gs` 内置的极简外部数据网容器，在 TCP `8080` 暴露 `/health` 端点作为绑定接口用户面探测目标。 |
| **PDU 会话** | UE 与 `ext-DN` 之间的逻辑 IPv4 数据连接，由 `DNN=oai`、切片 `SST=1` 与 `5QI=9` 标识。 |
| **数据时效性 / 证据质量（Telemetry Freshness / Evidence Quality）** | 独立于业务健康状态的可信度标签（`ok`、`stale`、`unavailable`、`unsupported`），用于防止使用过期样本误判在线状态。 |
| **协议 `186` 路由** | Jetson Console 管理的内核协议 `186` 默认 IPv4 路由规则：Wi-Fi 备用默认路由（`metric 5`）与蜂窝数据优先路由（`metric 10`）。 |
| **`QMAP / MPDN`** | Quectel RM520N-GL 固件中将蜂窝 PDU 上下文绑定至主机 RNDIS/ECM 数据网卡的多路复用/多 PDN 映射规则。 |
| **`boot_id` 防重放账本** | `boot_connect.py` 基于 Linux `/proc/sys/kernel/random/boot_id` 维护的单次启动执行记录，确保每次冷重启至多执行一轮自动入网编排。 |
| **ATR（Answer To Reset / 复位应答）** | 符合 ISO/IEC 7816 标准的智能卡上电复位十六进制响应字节串，承载传输协议参数（如 `T=0`）与厂商历史字节，用于在发送专用 APDU 指令前校验可编程 5G USIM 型号（如 `TB01`）。 |
