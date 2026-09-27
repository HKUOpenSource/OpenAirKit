# 开发准备审阅 — 2026-09-27

[English](2026-09-27-development-readiness.md)

审阅源码：`39dde4d0216dee973ed6cbf40ecb500e83c1ac74`，分支 `main`，初始工作区
干净。本地开发检查通过；实机验收前需先解决资源归属和管理链路保护问题。本次为
定向审阅，不关闭任何 Gate；[路线图](../roadmap.md)仍是唯一完成清单。

## 问题、范围与方法

问题：当前仓库和设备基线是什么，下一轮开发应按什么顺序进行？仓库没有
`.codegraph/` 索引，直接检查了架构、路线图、近期验收、CI、网络保护和生命周期
脚本。SSH 检查读取服务属性、USB 清单、项目容器状态、回环健康接口、选定的进程
身份与端口参数，以及发布文件哈希。已安装的生命周期 `status` 命令还会获取其
常规用户级锁。没有启动或停止服务、部署、写模组、修改路由或注入故障。
记录不包含连接地址、凭据和原始运行日志。

## 发现与开发顺序

1. **P1 — 启动流程没有在修改状态前拒绝已被占用的 Web 端口。**
   两端 Agentic-OCUDU 均已停止，但另一套已安装平台正在使用其配置端口。
   Spark 的 `oai-spark-web.service` 正在运行且启用自启，MainPID 的命令指定
   8877；`oai-spark-collector.service` 也在运行。Jetson 的 `oai-console.service`
   正在运行且启用自启，MainPID 指定 8878。它们与已停止的本项目服务不同。
   调用路径 `start.sh → Controller.preflight → Controller.start → maintain`
   在启动服务前没有检查监听归属。Spark 可能先启动核心网和无线，再发现 Web
   冲突；Jetson 可能先请求启动设备执行器，再遇到 Web 就绪失败。隔离模拟中，
   设置已有监听并注入应用启动失败后，Spark 仍请求 `core-start`、`radio-start`、
   `start`，Jetson 仍请求 `start`；两者监听检查次数均为零。这是模拟复现，
   没有实机尝试启动。应增加修改状态前的端口/资源归属检查、明确的冲突提示，
   并测试外部监听时零变更，以及自有健康服务的幂等启动。实机验收前明确站点
   资源归属，不能隐式停止另一套平台。

2. **P1 — 管理保护仍未验证隧道底层传输路径。**
   `network.inspect_management` 只确认 Wi-Fi 地址和经覆盖网络到 Spark 的路由，
   未确认隧道传输是否依赖模组。调用路径为 `Agent.auto_reconcile → recovery →
   Agent.write → Network.snapshot → inspect_management → modem.write`，另有
   `helper(protect) → inspect_management`。本次模拟仍在仅查询一次覆盖网络路由后
   返回 `management_protected=true`。若底层走 RNDIS，破坏性模组写操作可能导致
   管理连接中断。本次没有独立确认实际传输路径。应验证独立管理传输，在证据缺失、
   过期或变化时拒绝写操作；故障实测前覆盖 RNDIS 传输、有效独立路径、证据不可用
   和路径变化等回归场景。

3. **发布来源与 Jetson 验收仍不完整。**
   两端已安装清单仍标记基线 `fd3b3b0`、`dirty=true`。哈希匹配证明清单中文件的
   完整性，不证明与当前干净源码一致。下一候选包应来自干净提交；将已有安装和
   回滚记录对应到 P3-16/R06，补齐缺项。P3-GATE 前完成 P3-15 故障矩阵，以及
   P3-17 精确要求的五次停止/启动、重新接入与单控制者检查。9 月 24 日生命周期
   记录只覆盖一次循环。自动 CI 为 Python 3.12 / Node 22；Python 3.10/3.12 和
   浏览器矩阵需手动运行。保持被动流量与小流量诊断的现有产品范围。

## 设备基线

| 项目 | Spark | Jetson |
| --- | --- | --- |
| SSH / 架构 / Python | 可达 / aarch64 / 3.12.3 | 可达 / aarch64 / 3.10.12 |
| 已安装应用 | 0.2.0 | 0.5.1 |
| current 发布链接 | `5bc68497243efdf5` | `186b6c4659cc5e14` |
| 项目服务 | 三个监测服务及 V2 核心网、无线均 inactive；PID 为零 | 两个 V2 服务 inactive；PID 为零 |
| 自启策略 | 监测 disabled；核心网/无线 static | V2 服务 disabled |
| 项目运行状态 | 无项目核心网容器 | 设备 socket 不存在 |
| 清单文件哈希 | 28/28 匹配 | 48/48 匹配 |
| USB 硬件 | 检测到 B210 | 检测到 RM520N-GL |
| 根分区可用空间 | 约 2.8 TB | 约 189 GB |

被占用端口的公开健康响应分别为 Spark
`status=ok, version=0.2.0, collector=available` 和 Jetson
`status=ok, version=0.3.0`。它们属于另一套运行平台，不能证明 Agentic-OCUDU
健康或 UE 连通。本项目停用状态下没有新的注册、PDU、RAN 或用户面验收证据。
Jetson 两个退役的 `aoc-jetson-*` 服务仍为 failed、disabled，与 V2 分开判断。

清单 SHA-256 保持为：

- Spark：`d37822fdad93c2c5fe842411b32b2de348fefd7d218d3e8f4e01afcf83634a9e`。
- Jetson：`6757bdcdafcc5fc73b1bbd7d4395d7c05bbc209f8248f53c5bcb96806288be37`。

六个已安装操作脚本均与
[9 月 24 日生命周期记录](2026-09-24-platform-lifecycle.zh-CN.md)中的哈希一致。

## 验证与限制

`make check VENV=local/bootstrap-check` 通过：Jetson 58 项；Spark 52 项通过、
1 项已有 macOS peer-credential 跳过；共享协议栈/发布/生命周期 134 项通过。
合计 244 项通过、1 项跳过。TypeScript、文档、发布边界、许可证与 Shell 审计
通过。首次沙箱运行因共享 HTTP 测试无法绑定 localhost 而失败；允许回环监听后
完整重跑通过，没有修改测试。上述两个问题均在审阅版本上通过隔离模拟复现。

本地使用 Python 3.11.15、Node 24.14.0，以及已有依赖与前端构建产物。本轮未重跑
生产构建、浏览器 E2E、目标解释器矩阵、发布打包或实机安装/回滚。此前记录仅作为
历史依据。开发时使用上述显式环境；它不代表发布矩阵已经验收。本次文档更新了
审阅入口，并区分已安装版本和运行服务；没有修改应用行为。
