# 核心术语表

[English](glossary.md)

| 术语 | 定义说明 |
| --- | --- |
| **5G SA（独立组网）** | 5G NR 无线接入网（`OCUDU gNB`）通过 N2/N3 直接连接原生 5G 核心网（`Open5GS 5GC`），不依赖 4G LTE 锚点。 |
| **N2 / N3 / N4 / N6** | 3GPP 5G 架构关键接口：gNB-AMF 控制面（`N2`/NGAP）、gNB-UPF 用户面（`N3`/GTP-U）、SMF-UPF 会话控制（`N4`/PFCP）与 UPF-外部数据网（`N6`）。 |
| **`ext-DN`** | `aoc-v2-open5gs` 内部署的极简外部数据网容器，在 TCP `8080` 提供 `/health` 端点作为绑定接口数据面探测目标。 |
| **PDU 会话** | UE 与 `ext-DN` 之间的逻辑 IPv4 用户面通道，由 `DNN=oai`、切片 `SST=1` 与 `5QI=9` 标识。 |
| **证据质量（Evidence Quality）** | 独立于业务健康状态的可信度标签（`ok`、`stale`、`unavailable`、`unsupported`），防止使用过期样本误判在线状态。 |
| **协议 `186` 路由** | Jetson Console 管理的内核协议 `186` 默认 IPv4 路由：Wi-Fi 兜底（`metric 5`）与蜂窝数据优先（`metric 10`）。 |
| **`QMAP / MPDN`** | Quectel RM520N-GL 固件中将蜂窝 PDU 上下文与主机 RNDIS/ECM 网卡绑定的多路复用/多 PDN 规则。 |
| **`boot_id` 防重放账本** | `boot_connect.py` 基于 Linux `/proc/sys/kernel/random/boot_id` 维护的单次开机状态记录，确保每次冷启动至多执行一次自动入网编排。 |
| **ATR（Answer To Reset / 复位应答）** | 符合 ISO/IEC 7816 标准的智能卡上电复位响应字节串，包含传输协议参数（如 `T=0`）与厂商历史字节，用于在发送专用写卡 APDU 前核验白卡型号（例如 `TB01`）；不含任何订阅私钥或个人信息。 |
