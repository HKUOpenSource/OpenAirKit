# Agentic-OCUDU 路线图

本文件是当前唯一任务清单。任务只有在实现、测试和对应实机证据均满足要求时才勾选。
退役方案和一次性迁移材料不属于当前源码树、文档、构建或发布。

## 产品约定

- 单栈 5G SA 数据网络：OCUDU RAN + Open5GS 5GC。
- 单数据 PDU，DNN `oai`，当前地址池 `10.0.0.0/24`，默认 5QI 9。
- Spark Platform 和 Jetson Console 独立安装、升级、停止与回滚。
- Spark 只展示基站侧可获得的信息；Jetson 只展示 UE 侧可获得的信息。
- IMS、SIP、语音和固定时长观察不属于当前阶段门槛。
- 状态必须带证据质量；历史值、已有 IP 或一次 ping 不能单独证明连接。

## 准备阶段

- [x] V2-B01 建立代码、配置、状态、设备和网络资源清单。
- [x] V2-B02 保存部署前基线与可恢复备份。
- [x] V2-B03 固化 PLMN、TAC、切片、DNN、地址池和探测端点契约。
- [x] V2-B04 明确 Spark、Jetson、RAN、核心网和站点配置的所有权。
- [x] V2-B05 建立默认构建、安装和运行时的独立性检查。
- [x] V2-B06 建立敏感信息、发布边界和回滚审计。

## 第一阶段：OCUDU + Open5GS 数据网络

- [x] V2-P1-01 完成 Spark/B210/Jetson 实机盘点和只读基线。
- [x] V2-P1-02 固定 OCUDU 与 Open5GS 源码、镜像和 ARM64 构建输入。
- [x] V2-P1-03 构建并验证 Open5GS 数据核心网与订阅初始化。
- [x] V2-P1-04 完成独立 compose、N2/N3/N4/N6 和外部数据网配置。
- [x] V2-P1-05 验证标准 5G AKA、SQN 重同步和 AMF 恢复路径。
- [x] V2-P1-06 完成协议栈资源归属、启动、停止和失败保留诊断。
- [x] V2-P1-07 提供 `aoc-v2ctl preflight/prepare/start/stop/status`。
- [x] V2-P1-08 提供独立 UE 发现、连接、探测、benchmark 与清理工具。
- [x] V2-P1-09 验证活动 PDU 的 QFI 1 / 5QI 9 核心网证据；UE 动态查询标记为 unsupported。
- [x] V2-P1-10 验证单数据 PDU，不以残留 IMS/SOS 上下文作为失败条件。
- [x] V2-P1-11 验证真实注册、地址池、绑定接口路由和同次双向用户面。
- [x] V2-P1-12 优化实时 CPU、USB 缓冲和无线日志，闭环 underflow/late 证据。
- [x] V2-P1-13 完成同条件三次性能基线和 2T2R 对照，正式配置保留 1T1R。
- [x] V2-P1-14 验证 AMF、核心网和无线服务恢复后 UE 可重新接入。
- [x] V2-P1-GATE 完成数据网络、生命周期、恢复和性能实机验收。

当前正式无线基线：n78、20 MHz、30 kHz SCS、1T1R、TX/RX gain `80/68`、
UHD receive/send frames `64/64`。最优近距离实测约为上行 11.55 Mbps、下行
58.96 Mbps；结果受天线位置与信号质量影响，不能作为固定吞吐保证。依据见
[无线策略记录](acceptance/2026-09-11-radio-realtime-policy.md)和
[真实数据记录](acceptance/2026-09-09-v2-live-data.md)。

## 第二阶段：Spark Platform

- [x] V2-P2-01 建立独立 FastAPI、React/TypeScript、SQLite 与锁定依赖。
- [x] V2-P2-02 定义组件、链路、设备、会话、指标和证据的版本化契约。
- [x] V2-P2-03 采集主机、systemd、容器和 B210 状态。
- [x] V2-P2-04 采集 OCUDU JSON 指标、运行代次、RF 配置和异常计数。
- [x] V2-P2-05 采集 Open5GS NF、会话、QoS、N2/N3/N4/N6 证据。
- [x] V2-P2-06 实现基于明确证据与新鲜度的设备关联和连接判定。
- [x] V2-P2-07 完成 Overview、gNB、Core Network、Devices、Events 页面。
- [x] V2-P2-08 完成历史、诊断、鉴权 SSE、过期状态和数据库迁移。
- [x] V2-P2-09 完成受限 Operations、任务持久化、并发拒绝和审计。
- [x] V2-P2-10 完成 ARM64 离线发布、安装、停止和回滚工具。
- [x] V2-P2-11 完成真实 RAN、核心网、设备、链路和用户面数据验收。
- [x] V2-P2-12 完成统一英文信息架构、桌面/移动导航和页面交互验收。
- [x] V2-P2-GATE 完成独立安装、真实数据、状态失效、操作和回滚验收。

当前 Spark 源码与已安装版本为 `0.2.0`，配置监听 `127.0.0.1:8877`，默认不开机自启。
9 月 27 日 19:53 的只读检查确认本项目 core、radio 和 monitor 均运行，12 个核心网
容器健康且 N2 建链成功。已安装包的来源、当前三设备状态与下一轮优先问题见
[2026-09-27 三设备开发审阅](acceptance/2026-09-27-next-round-review.zh-CN.md)。

## 第三阶段：Jetson Console

- [x] V2-P3-01 完成 ARM64、Python、USB、串口、RNDIS、NetworkManager 和管理路由盘点。
- [x] V2-P3-02 建立独立 FastAPI、React/TypeScript、SQLite、配置与服务。
- [x] V2-P3-03 使用共享网络契约，不引入 gNB 实现选择或跨系统环境模式。
- [x] V2-P3-04 完成设备发现、进程锁、串口排他、命令队列和受限 Unix socket。
- [x] V2-P3-05 完成 SIM、驻留、注册、PDU、地址池、RNDIS 与数据路径分层状态。
- [x] V2-P3-06 完成自动/手动 Device Setup、变更预览、基线和回读。
- [x] V2-P3-07 完成任务持久化、版本冲突、取消、维护与重启中断处理。
- [x] V2-P3-08 完成自有路由 helper、管理连接保护和有限自动恢复。
- [x] V2-P3-09 完成用户启动的 Recover、单次重连、冷却和超时回读。
- [x] V2-P3-10 主动测速已于 0.4.0 退役；保留被动接口计数和小流量诊断。
- [x] V2-P3-11 完成 Overview、Device Setup、History、Settings 英文界面。
- [x] V2-P3-12 完成登录、CSRF、参数白名单、SSE、历史和脱敏导出。
- [x] V2-P3-13 部署至 `/opt/agentic-ocudu/jetson` 和 `127.0.0.1:8878`，默认不开机自启。
- [x] V2-P3-14 验证 Start/Stop/Status 的有界退出与重新启动。
- [ ] V2-P3-15 完成模拟器与实机故障矩阵，包括串口竞争、接口改名、注册/PDU 分裂、地址残留、任务取消和登录过期。
- [ ] V2-P3-16 完成升级、前版本回滚、重新安装和管理连接保留验收。
- [ ] V2-P3-17 完成五次停止/启动与重新接入循环，确认始终只有一个模组控制者。
- [ ] V2-P3-GATE 完成独立发布、数据业务、恢复、故障矩阵与可逆停用验收。

Jetson 源码与两台实机安装均为 `0.6.0`，配置监听 `127.0.0.1:8878`；9 月 27 日按用户要求
完成后续启用，OCUDU 核心网、无线和两台 Console 保持运行，双设备接入和绑定模组的数据探测通过。现有安装、回滚和
重新安装证据见 [0.5.1 部署记录](acceptance/2026-09-23-jetson-live-stream.zh-CN.md)；
独立安装与启停改进见 [0.6.0 开发验证](acceptance/2026-09-27-independent-lifecycle.zh-CN.md)；
双设备升级、独立启停和数据验证见 [0.6.0 实机验收](acceptance/2026-09-27-independent-lifecycle-deployment.zh-CN.md)。
P3-15、P3-16、P3-17、P3-GATE 与 R06 仍需按完整条件核对，不因版本升级自动完成。
同日 19:53 的[只读复核](acceptance/2026-09-27-next-round-review.zh-CN.md)确认两台
Console 继续运行并报告新鲜连接证据；自动恢复暂停，尚未重新执行独立数据探测。
历史 `0.3.0` 真实页面已显示
`5G data connection verified`，实测测速约为下载 60.7 Mbps、上传 12.1 Mbps、
延迟 26.9 ms、抖动 0.3 ms、丢包 0%；这些结果不代替尚未完成的故障与回滚任务。

## 工程与文档整理

- [x] V2-R01 将 Jetson、Spark、OCUDU、Open5GS 与部署工具迁入明确目录。
- [x] V2-R02 建立两个平台的独立版本、构建入口和发布边界。
- [x] V2-R03 建立根级贡献、安全、变更、发布和 CI 规范。
- [x] V2-R04 建立当前中英文文档集合并从当前源码树移出退役资料。[验收记录](acceptance/2026-09-14-documentation-boundary.md)
- [x] V2-R05 增加文档链接、配对、陈旧路径和外部项目引用审计。[验收记录](acceptance/2026-09-14-documentation-boundary.md)
- [ ] V2-R06 在目录迁移后的 ARM64 包上分别完成安装、回滚和重新安装。

## 阶段完成条件

阶段 Gate 必须有对应代码测试、发布审计和实机证据。失败、跳过或尚未执行的项目
保持未勾选。发布包不得包含 `archive/`、另一平台、生产配置、凭据、数据库、日志、
抓包、缓存、符号链接或未锁定依赖。
