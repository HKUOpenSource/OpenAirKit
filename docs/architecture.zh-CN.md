# 架构

## 产品边界

Agentic-OCUDU 提供一套 5G SA 数据网络：OCUDU 提供 RAN，Open5GS 提供 5G
核心网；Spark Platform 负责基站侧监测与受限操作；Jetson Console 负责 UE
模组监测与受限操作。IMS、SIP 和语音服务不属于当前产品范围。

```text
Jetson Console (127.0.0.1:8878) -> RM520N 模组 -> B210 / OCUDU gNB -> Open5GS -> 外部数据网
                                                        |
                                        127.0.0.1:8879（JSON 指标，仅 root 可访问 nftables 守护）
                                                        |
                                          Spark Platform (127.0.0.1:8877)
```

## 组件归属

| 组件 | 拥有 | 不得拥有 |
| --- | --- | --- |
| Jetson Console（`0.6.2`） | 模组锁、受限 AT 流程、协议 186 自有路由、UE 状态、`127.0.0.1:8878` | RAN/核心网生命周期或任意 shell |
| Spark Platform（`0.2.1`） | 主机/RAN/核心网证据、历史、事件、受限栈任务、`127.0.0.1:8877` | 模组控制或仅 UE 可见的信息 |
| OCUDU 栈 | B210（`rx_gain=54`、`tx_gain=80`、`pusch.max_ue_mcs=24`）、小区配置、NGAP、`127.0.0.1:8879` 指标、`aoc-v2-cpu-latency` | Web 会话或平台数据 |
| Open5GS 栈 | 注册、PDU、策略、N3/N4/N6（`aoc-v2-open5gs-core`）、MongoDB（7.0+ 内核 `GLIBC_TUNABLES`） | 无线硬件或 UI 状态 |

## 运行时、UI 与权限边界

- **共享 UI 边界**：两个 React 控制台共用 [`packages/console-ui`](../packages/console-ui/README.zh-CN.md)（`Astryx Core`、`Charts`、`Neutral` 主题与 `UIProvider`），各自仅维护本地设备状态，不引入全局设备集群状态层。
- **权限隔离**：两端 Web 服务（Spark 的 `aoc-web`、Jetson 的 `aoc-v2-jetson-web`）以非特权账户运行，不能直接访问 Docker socket 或串口设备。需要特权的操作通过本机执行器（`aoc-control` / `aoc-v2-jetson-device`）或 `/usr/local/sbin/aoc-maintain`（`deploy/maintenance/`）执行，后者只接收 SHA-256 批准包与固定操作白名单（`NOPASSWD: NOSETENV`）。
- **回环端口隔离**：Spark Web 监听 `127.0.0.1:8877`，Jetson Web 监听 `127.0.0.1:8878`，OCUDU JSON remote-control 指标端口位于 `127.0.0.1:8879`，并由 `aoc-v2-metrics-guard.service`（`table inet aoc_v2_metrics_guard` 拒绝 `skuid != 0`）限制访问，从而避开 DGX Spark 共驻推理服务占用的 `127.0.0.1:8000–8002`。
- **主机与硬件适配**：Spark 侧 `collector.py::bridge_interface()` 通过 `docker network inspect` 动态解析核心网网桥接口名（同时兼容 `br-<id12>` 与显式命名网桥）；`deploy/spark/stack/` 提供 `/dev/cpu_dma_latency` 低时延守护（`aoc-v2-cpu-latency.service`）及面向 7.0+ 内核的 MongoDB `GLIBC_TUNABLES=glibc.pthread.rseq=1`。Jetson 侧 `hardware.py::discover()` 支持 Quectel RM520N 的 RNDIS（`00/01` -> AT `04`）与 ECM `cdc_ether`（`04` 或 `0a` -> AT `02`）拓扑校验，发现不匹配时在打开串口前即拒绝执行。
- **可选开机协调器**：按需部署时，`deploy/jetson/boot_connect.py` 独立于只读应用发布包安装在 `/opt/agentic-ocudu/jetson/boot_connect.py`，通过 root 私有的 `/etc/aoc-v2-jetson/boot.json` 校验发布与配置哈希，在启动执行器前等待 USB、Wi-Fi 和 Tailscale 就绪，并在每次开机最多执行一次标准入网流程（不保存 SIM 鉴权密钥）。

## 网络契约

共享契约保存在 `config/network-contract.json`。当前部署使用 PLMN `460/03`、
DNN `oai`、一个 IPv4 数据 PDU 和配置的 `10.0.0.0/24` UE 地址池。站点地址和
凭据不进入仓库。

## 状态语义

证据质量与业务健康相互独立。`ok`、`stale`、`unavailable`、`unsupported`
说明数值是否可信；运行、健康、连接描述业务状态。只有新鲜的注册、PDU、地址池、
RAN 上下文和用户面证据一致时，UE 才显示为已连接。历史日志、已有 IP 或一次 ping
都不能单独证明当前连接。

采集器保存来源时间和进程代次。服务重启、日志轮转或计数器归零会开启新的观测
区间，避免旧设备在线、虚假零流量和速率尖峰。
