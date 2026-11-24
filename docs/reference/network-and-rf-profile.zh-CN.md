# 网络契约、射频基线与接入策略参考

[English](network-and-rf-profile.md)

本文档是 `config/network-contract.json` 与 `deploy/spark/stack/runtime.py` 所定义射频基线、
5G SA 核心网契约及 UE 接入判定语义的唯一参考来源。

## 无线射频基线（`OCUDU gNB` + `USRP B210`）

| 参数项 | 默认基线值 | 定义来源 |
| --- | --- | --- |
| 工作频段 | Band `n78` | `config/network-contract.json` |
| 信道带宽 | `20 MHz` | `config/network-contract.json` |
| 子载波间隔（SCS） | `30 kHz` | `config/network-contract.json` |
| 天线 / MIMO 配置 | `1T1R` | `deploy/spark/stack/runtime.py` |
| 载波中心频点（ARFCN） | `643392` | `config/network-contract.json` |
| 物理小区标识（PCI） | `666` | `config/network-contract.json` |
| TDD 时隙配比 | `5 ms` 周期（`7 DL / 2 UL / 6 DL sym / 4 UL sym`） | `config/network-contract.json` |
| UHD B210 增益 | `tx_gain=80`、`rx_gain=54` | `deploy/spark/stack/runtime.py` |
| 上行最大 UE MCS | `cell_cfg.pusch.max_ue_mcs=24` | `deploy/spark/stack/runtime.py` |
| UHD 收发帧缓冲 | `64 / 64` | `deploy/spark/stack/runtime.py` |

## 5G 核心网与数据 PDU 契约（`Open5GS 5GC`）

| 参数项 | 契约值 | 范围与说明 |
| --- | --- | --- |
| PLMN | `460/03` | 须与 USIM 卡内 IMSI 前缀一致 |
| 跟踪区码（TAC） | `1` | 单小区 SA 部署 |
| 切片 SST | `1` | 默认数据切片（不限定 SD） |
| PDU 会话类型 | 单 `IPv4` 数据 PDU | 专注 5G SA 数据面传输 |
| 数据网络名（`DNN`） | `oai` | Open5GS 策略与 Jetson Device Setup 共用 |
| UE IPv4 地址池 | `10.0.0.0/24` | 作为 Jetson 连通性校验依据 |
| QoS `5QI` | `9` | 默认非 GBR 数据承载（核心网侧对应 `QFI 1`） |
| 外部数据网探测端点 | `ext-DN` 容器 TCP `8080 /health` | 位于 `aoc-v2-open5gs` 内部，专供绑定接口小流量探测 |

## UE 配置分区与策略模型

Jetson Console 将运行时预期配置划分为 5 个独立分区：

| 配置分区 | 包含内容 | 运行时行为 |
| --- | --- | --- |
| `network` | PLMN、切片 `SST`、`DNN` 与期望 IPv4 地址池 | 在 Device Setup 中校验；修改后只更新本机期望，不会隐式修改 Open5GS |
| `selection` | `rat: "NR5G-SA"`、`mode: "observe_only"`、目标频段、可选 PCI 与 SSB ARFCN | 仅对比实际服务小区是否匹配，不下发模组锁频或锁小区命令 |
| `diagnostics` | 绑定探测地址（`gateway`、`upf`、`ext_dn`、`public`）及必选探测项 | 至少启用两个独立绑定目标以验证数据面可达性 |
| `management` | `wifi_interface`、`tailscale_interface`（`tailscale0`）、`spark_address` | 在允许写操作前确认带外管理通路受保护 |
| `recovery` | `natural_wait_seconds`、`max_attempts`、`cooldown_seconds` | 约束断网后自动恢复的等待、次数与冷却时长 |

注意：`radio_reference` 中的载波中心 ARFCN 仅供运维参考，不等同于服务 SSB ARFCN；
将 `pci` 与 `ssb_arfcn` 设为 `null` 可放宽小区匹配观测条件。

## 独立状态指标与证据质量语义

两个控制台严格区分 **业务健康状态** 与 **证据质量**：

- **证据质量状态**：
  - `ok`：数据采集在有效新鲜窗口内。
  - `stale`：样本超出新鲜度上限（如 Jetson 超过 `20 s`）。
  - `unavailable`：采集器或设备接口当前无法读取实时状态。
  - `unsupported`：当前运行构建不提供该指标域。
- **UE 已连接判定条件**：仅当新鲜 SIM 状态、`460/03` NR SA 注册、`10.0.0.0/24`
  活动 IPv4 PDU、RNDIS/ECM 接口地址、当前 gNB 上下文及绑定接口探测全部一致时，
  设备才报告 `connected`。一旦发生注册、服务小区、PDU 或网卡接口变更，旧探测证据立即失效。
- **进程代次跟踪**：采集器随快照记录来源时间戳与进程代次，服务重启或计数器归零时
  自动开启新观测区间，避免产生虚假零流量或速率尖峰。
