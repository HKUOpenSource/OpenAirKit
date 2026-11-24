# 网络契约、射频基线与接入策略参考

[English](network-and-rf-profile.md)

本文档为 `config/network-contract.json` 与 `deploy/spark/stack/runtime.py` 所定义射频基线、
5G SA 核心网契约及 UE 接入判定语义的权威参考基准。

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
| 数据网络名（`DNN`） | `oai` | Open5GS UPF 策略与 Jetson Device Setup 共用 |
| UE IPv4 地址池 | `10.0.0.0/24` | 作为 Jetson 连通性探测校验基准 |
| QoS `5QI` | `9` | 默认非 GBR 数据承载（核心网侧对应 `QFI 1`） |
| 外部数据网探测端点 | `ext-DN` 容器 TCP `8080 /health` | 位于 `aoc-v2-open5gs` 内部，供绑定接口数据面探测使用 |

## UE 配置分区与策略模型

Jetson Console 将运行时配置划分为 5 个独立策略分区：

| 配置分区 | 包含内容 | 运行时行为 |
| --- | --- | --- |
| `network` | PLMN、切片 `SST`、`DNN` 与预期 IPv4 地址池 | 在 Device Setup 中校验；修改后仅更新本机预期，不会隐式修改 Open5GS |
| `selection` | `rat: "NR5G-SA"`、`mode: "observe_only"`、目标频段、可选 PCI 与 SSB ARFCN | 仅对比实际服务小区是否匹配，不下发模组锁频或锁小区命令 |
| `diagnostics` | 绑定探测地址（`gateway`、`upf`、`ext_dn`、`public`）及必选探测项 | 至少启用两个独立绑定目标以验证数据面转发可达 |
| `management` | `wifi_interface`、`tailscale_interface`（`tailscale0`）、`spark_address` | 在执行任何路由写操作前核验带外管理通路受保护 |
| `recovery` | `natural_wait_seconds`、`max_attempts`、`cooldown_seconds` | 约束链路中断后的自动恢复等待窗口、重试上限与冷却间隔 |

注：`radio_reference` 中的载波中心 ARFCN 仅供运维参考，不等同于服务小区 SSB ARFCN；
将 `pci` 与 `ssb_arfcn` 设为 `null` 可放宽小区匹配观测条件。

## 独立状态指标与数据时效性语义

两个控制台均将 **业务健康状态** 与 **数据时效性** 严格解耦：

- **数据时效性状态**：
  - `ok`：样本在有效采样时间窗口内。
  - `stale`：样本已超出时效上限（如 Jetson 端超过 `20 s`）。
  - `unavailable`：采集器或设备接口当前未能读取有效状态。
  - `unsupported`：当前运行构建不提供该指标字段。
- **UE 已连接判定条件**：仅当有效期内 USIM 状态、`460/03` NR SA 注册、`10.0.0.0/24`
  活动 IPv4 PDU、RNDIS/ECM 网卡地址、当前 gNB 上下文及绑定接口探测全部一致时，
  状态方才报告 `connected`。一旦发生注册、服务小区、PDU 会话或网卡变更，历史探测
  结果立即失效。
- **进程实例代次跟踪**：采集器随快照记录来源时间戳与进程实例代次（Generation ID），
  在服务重启或计数器归零时开启干净观测区间，避免产生虚假零流量或速率尖峰。
