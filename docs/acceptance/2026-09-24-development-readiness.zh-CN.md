# 开发准备审阅 — 2026-09-24

[English](2026-09-24-development-readiness.md)

审阅源码：`dba599c830f2abe6a09309ca85a52afd281519cf`，分支 `main`，初始工作区干净。
当前可以开始本地开发；会中断连接的 Jetson 实机验收应先处理下述管理链路保护问题。
本记录不关闭任何 Gate；[路线图](../roadmap.md)仍是唯一任务清单。

## 范围与方法

问题：当前源码与设备基线是什么，下一轮应优先处理什么？仓库没有 `.codegraph/`
索引，直接检查了架构、路线图、近期验收记录、CI／构建／测试入口、Jetson 网络／
恢复／API 调用路径和受限维护状态。这是有范围的开发准备审阅，不是全面代码或安全审计。

实机检查使用只读 SSH、systemd 属性、USB／容器清单、回环健康接口、已安装 manifest
哈希及既有受限 `aoc-maintain ue-status` 操作。本轮未部署、重启服务、写入模组、
修改路由或注入故障。记录省略私有地址和原始日志。

## 发现与下一轮顺序

1. **P1：管理保护仍不能证明底层传输独立。**
   `apps/jetson-console/backend/aoc_jetson/network.py:82–99` 只检查 Wi-Fi 地址和
   到 Spark 的覆盖网络路由，没有检查 Tailscale 底层传输使用 Wi-Fi 还是模组数据路径。
   调用链为 `Agent.auto_reconcile → recovery job → Agent.write → Network.snapshot →
   inspect_management → modem.write`，以及 `helper(protect) → inspect_management`。
   在当前版本的 mock 复现中，仅查询一次覆盖网络目的地址，就返回
   `management_protected=true`。当覆盖网络依赖 RNDIS 时，重连可能切断管理连接。
   本轮未判定实机当前隧道传输路径，也未制造中断。下一步应建立独立管理传输证据，
   在证据缺失、过期或变化时拒绝破坏性写入；覆盖“隧道经过 RNDIS”、有效独立路径、
   证据不可用及路径切换的回归，再进行破坏性实机验收。这确认了
   [上轮审阅](2026-09-23-next-round-review.zh-CN.md)中的未解决项。

2. **发布证据需要与当前提交对齐。**
   两台设备 manifest 均记录基线 `fd3b3b0`、`dirty=true`。全部清单文件与其哈希匹配，
   只能证明包内完整性，不能证明与干净的 `dba599c` 等价。既有
   [Astryx 部署](2026-09-23-astryx-deployment.zh-CN.md)和
   [Jetson 0.5.1 部署](2026-09-23-jetson-live-stream.zh-CN.md)已包含回滚与重新安装。
   应先对照 P3-16／R06 复用有效证据，再决定重测范围。下一候选包应从干净提交构建，
   执行目标版本与浏览器发布检查，记录备份和 manifest 哈希，补齐安装、回滚及管理连接
   保留证据。本轮未构建发布归档，也未重复部署。

3. **完成 Jetson 剩余验收条件。**
   P3-15 需要完整模拟器／实机故障矩阵，P3-17 需要五次停止／启动／重新接入循环并确认
   单一模组控制者，P3-GATE 保持未完成。以往无线服务循环和正常健康状态不能替代这些
   条件。当前自动恢复暂停，恢复验收设计应明确考虑该状态。保持被动计数和小流量诊断
   的产品范围，主动吞吐任务继续退役。

上轮 P2 被动速率问题已在当前源码修复：`Agent.sample → Network.snapshot` 跟踪接口名
和 ifindex，失败时清空基线，并使用单调时钟计算时间差；七项相关回归通过。
README 与路线图版本描述已陈旧，本轮更新为 Jetson 0.5.1／Spark 0.2.0，并将文档导航
指向本记录；不改变路线图勾选状态或应用行为。

## 实机观测基线

| 项目 | Spark | Jetson |
| --- | --- | --- |
| 架构／Python | aarch64／3.12.3 | aarch64／3.10.12 |
| 应用版本 | 0.2.0 | 0.5.1 |
| 当前 release | `5bc68497243efdf5` | `186b6c4659cc5e14` |
| 公共健康接口 | status／collector 为 `ok` | status／web／device 为 `ok` |
| 应用服务 | 三个 active，自动重启为零 | 两个 V2 active，自动重启为零 |
| 开机策略／监听 | disabled／`127.0.0.1:8877` | disabled／`127.0.0.1:8878` |
| Manifest 文件哈希 | 28/28 匹配 | 48/48 匹配 |
| 硬件 | 检出 USRP B210 | 检出 Quectel RM520N-GL |
| 根分区可用空间 | 约 2.8 TB | 约 192 GB |

Spark 无线服务 active，项目的 12 个核心网／数据网容器均为 healthy；另有其他容器负载。
Jetson 两个退役服务仍为 failed、disabled，与正常运行的 V2 服务分开看待。受限状态接口
报告新鲜的 `quality=ok`、已注册、数据 PDU 激活、实验室策略匹配且 RNDIS 绑定数据路径
验证成功；`maintenance=false`、`recovery_paused=true`。其中
`management_protected=true` 仍受上述代码缺口限制。这是运行中执行器的状态，不能替代
一次独立关联 Spark／Jetson 的端到端验收，也不是登录浏览器后的页面检查。

Manifest SHA-256：

- Spark：`d37822fdad93c2c5fe842411b32b2de348fefd7d218d3e8f4e01afcf83634a9e`。
- Jetson：`6757bdcdafcc5fc73b1bbd7d4395d7c05bbc209f8248f53c5bcb96806288be37`。

## 本地验证与边界

- `make ci VENV=local/bootstrap-check` 通过：Jetson 58 项通过；Spark 52 项通过，
  1 项 macOS peer-credential 检查跳过；共享栈／发布 102 项通过。两个生产前端构建、
  TypeScript、文档／发布边界／许可证／Shell 审计全部通过。Vite 仍提示已有的
  大于 500 kB 分块。
- 首次 `make check` 因沙箱禁止监听 localhost，在共享测试处中断。获得回环权限后完整
  CI 通过，没有修改或削弱测试。
- `make e2e-jetson e2e-spark VENV=local/bootstrap-check` 通过：Jetson 浏览器套件无失败，
  Spark 三个套件全部通过，覆盖桌面／移动布局、证据过期、实时流丢失和登录过期。
  这些检查使用隔离的合成服务，不是实机验收证据。
- 文档更新后，`make docs-audit VENV=local/bootstrap-check` 对全部 80 份当前文档通过，
  `git diff --check` 通过。
- 默认 `.venv` 为不受支持的 Python 3.9.6；本轮显式环境使用 Python 3.11.15。
  本地 Node 为 24.14.0，CI 指定 Node 22。本轮不能认证原生 Python 3.10／3.12 矩阵
  或 Node 22 行为。Spark 系统 Node 18 也不构成前端构建环境验证；部署使用预构建资产。

本轮文档记录了问题、影响调用链、运行影响和验证结果，未加入生产配置或连接地址。
