# 产品路线图

[English](roadmap.md)

本路线图记录 **5G SA 协议栈**、**双端本地管控平台** 与 **未来社区 DIY AI 生态**
的阶段里程碑。已完成条目均有对应源码实现、自动化测试与实机验收基线作为支撑
（见[实机验收基线](acceptance/README.md)）。

## 核心设计约定

- **单栈 5G SA IPv4 数据网络**：**OCUDU** RAN + **Open5GS** 5GC（具体参数见[网络与射频基线](reference/network-and-rf-profile.zh-CN.md)）。
- **双端独立生命周期**：Spark Platform 与 Jetson Console 各自维护本机状态，支持独立安装、升级、停止与回滚。
- **证据驱动状态判定**：UE 在线状态需经新鲜 SIM、NR SA 注册、活动 IPv4 PDU、RAN 上下文与绑定接口探测共同验证。

## 里程碑 1 — 可复现 5G SA 协议栈（`已完成`）

- [x] 固定版本 ARM64 **OCUDU** gNB 构建、USRP B210 探针与实时低时延保障（`aoc-v2ctl` 生命周期控制器）。
- [x] 固定版本 **Open5GS** + **MongoDB** ARM64 容器构建/校验流程与 per-UE 独立开户工具（`stacks/open5gs/subscriber.py`）。
- [x] 启动自动校验 N2 NG Setup 与失败现场诊断保留。
- [x] 实机验证 5G AKA 鉴权、SQN 同步、AMF 恢复与多 UE 并发调度。

## 里程碑 2 — Spark Platform（`已完成`）

- [x] 非特权 FastAPI + Astryx React 控制台（`127.0.0.1:8877`），支持时序指标索引与持久 SSE 实时推送。
- [x] 将 OCUDU JSON 指标端口隔离至 `127.0.0.1:8879` 并启用 root 守护，留空 `127.0.0.1:8000–8002` 供共驻 AI 推理服务使用。
- [x] 运行时动态发现 Open5GS 网桥、采集网元与 N2/N3/N4/N6 证据、关联 UE 上下文并提供受限运维审计日志。
- [x] 离线 ARM64 安装、回滚与多机硬件联调验收。

## 里程碑 3 — Jetson Console 与无人值守自愈（`进行中`）

- [x] 兼容安装于 Jetson Orin M.2 载板的 Quectel RM520N-GL RNDIS 与 ECM USB 拓扑发现与校验。
- [x] 串口独占锁、Device Setup 变更预览与基线回读，以及分离式网络/选网/探测/恢复策略配置。
- [x] 双路径 IPv4 默认路由自动切换（`Wi-Fi` 兜底 <-> 蜂窝优先）、管理通路校验与有界自愈流程。
- [x] 可选冷重启开机协调器（`boot_connect.py`）通过无人值守真实冷重启验证。
- [ ] 扩展自动化故障矩阵复测与目录重构后 ARM64 安装/回滚回归门禁。

## 里程碑 4 — 社区 DIY AI 扩展生态（`规划中`）

- [x] 完成双端预留算力隔离与 REST/SSE 接入指南（[双端 AI 定制指南](ai-customization.zh-CN.md)）。
- [ ] 提供 DGX Spark（`127.0.0.1:8000–8002`）消费 Spark SSE 与事件的参考智能体示例。
- [ ] 提供 Jetson Orin 消费 Jetson Console 遥测的边缘推理动态卸载参考示例。
