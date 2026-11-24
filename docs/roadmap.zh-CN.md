# 产品路线图

[English](roadmap.md)

本路线图记录 **5G SA 协议栈**、**双端本地管控平台** 与 **未来社区 DIY AI 生态** 的阶段里程碑。
已勾选条目均有对应源码、自动化测试与脱敏实机基线作为支撑（见[实机验收基线](acceptance/README.md)）。

## 产品边界约定

- **单栈 5G SA 数据网络**：**OCUDU** RAN + **Open5GS** 5GC（`DNN=oai`、IPv4 地址池 `10.0.0.0/24`、`5QI=9`）。
- **独立生命周期**：Spark Platform 与 Jetson Console 独立安装、升级、停止与回滚，各自仅维护本机状态。
- **证据驱动状态判定**：仅有历史日志、已有 IPv4 地址或单次 ping 不能判定 UE 已连接，必须以新鲜的 SIM、注册、PDU、RAN 与绑定探测一致为前提。
- IMS、SIP、语音业务及主动大流量测速门槛不在当前阶段范围内。

## 里程碑 1 — 可复现 5G SA 协议栈（`已完成`）

- [x] 固定版本 ARM64 **OCUDU** gNB 构建、USRP B210 探针与实时低时延守护（`aoc-v2-cpu-latency`、`rx_gain=54`、`tx_gain=80`、`pusch.max_ue_mcs=24`）。
- [x] 固定版本 **Open5GS 2.8.0** + **MongoDB 8.0.30** 镜像构建、`GLIBC_TUNABLES` Linux 7.0+ 内核兼容以及每台 UE 独立开户工具（`stacks/open5gs/subscriber.py`）。
- [x] 独立协议栈控制器 `aoc-v2ctl`（`preflight`、`prepare`、`start`、`status`、`stop`），验证 SCTP 与 N2 NG Setup 并保留失败诊断现场。
- [x] 实机验证 5G AKA 鉴权、SQN 同步、AMF 重启恢复与双 UE 并发调度。

## 里程碑 2 — Spark Platform `0.2.1`（`已完成`）

- [x] 非特权 FastAPI + React/TypeScript（Astryx UI）控制台，监听 `127.0.0.1:8877`，支持 schema 6 时序索引与长连接 SSE 推送。
- [x] 将 OCUDU JSON 指标端口迁至 `ws://127.0.0.1:8879`（`aoc-v2-metrics-guard` nftables 守护），确保 `127.0.0.1:8000–8002` 留空供 Spark 上共驻 AI 推理服务使用。
- [x] 动态 Docker 网桥发现（`collector.py::bridge_interface()`）、Open5GS 网元与 N2/N3/N4/N6 证据采集、基于明确证据的 UE 设备关联与受控操作审计。
- [x] 离线 ARM64 安装、回滚与多机联调实机验收。

## 里程碑 3 — Jetson Console `0.6.2` 与无人值守自愈（`进行中`）

- [x] 兼容安装于 Jetson Orin M.2 载板上的 RM520N-GL RNDIS（`00/01` -> AT `04`）与 ECM `cdc_ether`（`04`/`0a` -> AT `02`）USB 拓扑发现与校验。
- [x] 串口独占锁、Device Setup 变更预览与基线回读、schema 3 网络/选网/探测/管理/恢复策略拆分。
- [x] 协议 `186` 双路径默认路由自动切换（Wi-Fi 兜底 metric `5` <-> 蜂窝优先 metric `10`）、管理保护核验及有界恢复（`120 s` 等待 / 最多 2 次 / `300 s` 冷却）。
- [x] 可选冷重启协调器（`boot_connect.py`）通过多机真实冷重启闭环验证。
- [ ] 扩展自动化故障矩阵复测（串口竞争、接口改名并发、注册/PDU 状态分裂、会话过期）及目录重构后 ARM64 安装/回滚全流程复验。

## 里程碑 4 — 社区 DIY AI 扩展生态（`规划中`）

- [x] 完成双端预留算力边界与 REST/SSE 接入文档规范（[双端 AI 定制指南](ai-customization.zh-CN.md)）。
- [ ] 提供 DGX Spark 侧（`127.0.0.1:8000–8002`）订阅 Spark SSE 与事件的 DIY 参考示例。
- [ ] 提供 Jetson Orin 侧消费 `/api/v1/status` 与 `/api/v1/events/stream` 的边缘侧智能决策参考示例。
