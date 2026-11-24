# 下一轮开发审阅 — 2026-09-27

[English](2026-09-27-next-round-review.md)

后续进展：下述三项 P1 已有[源码修复与回归证据](2026-09-27-p1-reliability-fixes.zh-CN.md)。
后续[部署证据](2026-09-27-ui-deployment.zh-CN.md)记录了上线结果，本审阅保留修复前的原始基线。

审阅版本：`87e059fd5b4010384606eca6180bd0f3ecc86aa1`，起始 `main` 工作区干净。
当前三台设备正在运行 OCUDU。本地构建和测试通过，但继续扩展实机验收前应先处理
以下失败路径。本记录不关闭任何[路线图](../roadmap.md) Gate。

## 范围与证据

审阅问题：当前源码和三台设备的基线是什么，生命周期合并后还存在哪些问题，
下一轮应先开发什么？仓库没有 `.codegraph/` 索引，因此直接检查源码。范围包括
两个应用、生命周期和发布工具、订阅维护、测试以及按时间顺序核对的验收记录。
下述结论分别标明隔离合成数据复现与静态分析。

SSH 观测时间为 9 月 27 日香港时间约 19:53。读取了指定 systemd 属性、回环健康
接口、项目容器状态、N2 信息、已安装文件校验和及 USB 产品 ID。两台 Jetson 通过
已有受限 `ue-status` 操作读取过滤后的快照，使用维护 helper 的正常锁。本轮未执行
服务切换、部署、模组写入、路由变更、新的数据探测或故障注入。记录不含设备地址、
凭据、订阅者身份和原始运行日志。

## 当前设备基线

Jetson A、B 分别对应本次提供的第一台和第二台 Jetson。

| 证据 | Spark | Jetson A | Jetson B |
| --- | --- | --- | --- |
| SSH / 架构 | 可达 / ARM64 | 可达 / ARM64 | 可达 / ARM64 |
| Python | 3.12.3 | 3.10.12 | 3.10.12 |
| 已安装应用 | 0.2.0 | 0.6.0 | 0.6.0 |
| 发布 ID | `5bc68497243efdf5` | `8ade791a3317ad5e` | `8ade791a3317ad5e` |
| manifest 文件匹配 | 28/28 | 51/51 | 51/51 |
| 项目服务 | core 为 active/exited；radio 与三个 monitor 服务为 active/running | device 与 Web 为 active/running | device 与 Web 为 active/running |
| 自动重启计数 | 全部为零 | 均为零 | 均为零 |
| 应用公开健康接口 | OK，collector OK | OK，Web OK | OK，Web OK |
| USB 产品 | B210 | Quectel 模组 | Quectel 模组 |
| 当前 UE 证据 | 本轮未独立重新关联 | 质量 OK；已注册；PDU 活动；已连接 | 质量 OK；已注册；PDU 活动；已连接 |
| 观测 / 自动恢复 | — | 开启 / 暂停 | 开启 / 暂停 |

12 个项目核心网容器全部运行且健康；当前 N2 响应包含一个已成功建链的 gNB。
两台 UE 快照在采集时约为 13–15 秒前的证据，均报告连接已验证。本轮没有重新执行
[部署验收](2026-09-27-independent-lifecycle-deployment.zh-CN.md)中的独立绑定接口探测。

两台 Jetson 均报告管理连接受保护，主路由表 IPv4 默认路由接口仅有 Wi-Fi。
这不等于独立确认了隧道实际传输链路及其策略路由。SSH 普通用户不能检查受保护的
设备 socket 目录，但已有授权的状态 RPC 成功。

另一套平台的已检查服务均未运行，但其中一些仍启用开机自启。项目 monitor 与
Jetson 服务禁用自启，项目 core/radio 单元为 static。因此，不能把重启当作恢复
当前 OCUDU 运行基线的已验证方式；重启验收前需选定并核实资源归属。

发布 manifest SHA-256：

- Spark：`d37822fdad93c2c5fe842411b32b2de348fefd7d218d3e8f4e01afcf83634a9e`。
- 两台 Jetson：`e297880d5a4ac2ec4f04395efbf76e113d7e61c62a977c62a8f0edee1340ae40`。

已安装 Spark 和 Jetson 生命周期控制器与当前源码哈希一致，分别为
`b2867227b14f3678824cdb214bcea6c858c0430beaf7c4d028c4775db785549a`
和 `eed4dced9dbf8f9a87c827c4d8f48ee7fc804b49a9b6fd9b4ee027f20c72b453`。
应用 manifest 仍记录 `dirty=true`，Spark 基于 `fd3b3b0`，Jetson 基于 `39dde4d`。
文件匹配证明清单内文件完整，不能证明全部内容等同于干净的当前 HEAD。下一次发布
应从干净提交构建并保存来源信息。

## 已确认的代码问题

### P1 — CFUN 回读失败可能让模组停留在关闭状态

调用路径：`Agent.execute → Agent.write(cfun0) → Modem.write → exchange →
query(AT+CFUN?)`。位置为 [agent.py](../../apps/jetson-console/backend/aoc_jetson/agent.py)
第 383、412 行和 [modem.py](../../apps/jetson-console/backend/aoc_jetson/modem.py)
第 224–230 行。CFUN=0 已生效但应答或回读失败时，异常跳过 CFUN=1；失败清理只处理
网络路由，而电源恢复授权也要等回读成功才设置。隔离恢复任务复现结果为任务失败、
functionality 为 0、写入历史只有 `cfun0`，且恢复暂停。尚未测量实机触发情况。

应对写入结果不确定的情况增加有界电源恢复处理。测试应覆盖应答丢失、回读失败、
取消和 CFUN=1 失败，并始终保留模组独占与独立管理链路保护。

### P1 — Spark 控制连接 EOF 后，未结束的任务阻塞后续操作

调用路径：`POST /control → run_control → control_messages → reader.readline`，
位置为 [web.py](../../apps/spark-console/backend/aoc_spark/web.py) 第 83–85、118–130 行。
收到 `running` 后连接 EOF 会正常结束迭代，绕过调用 `poll_control` 的异常处理。
持久化任务一直为 running，[storage.py](../../apps/spark-console/backend/aoc_spark/storage.py)
第 132 行会拒绝后续操作。隔离 `running → EOF` 复现中，下一任务得到
`operation_in_progress`。Web 启动时的协调逻辑可以恢复，但持续运行的进程不会协调
此正常 EOF 路径。

应在流结束时恢复查询或终结未完成任务，覆盖首条消息前、running 后和终态后的 EOF，
同时避免重复执行操作。

### P1 — Spark 在发现外部 Web 监听冲突前已经启动协议栈

调用路径：`start.sh → Controller.start → core-start → radio-start → start`，
位置为 [platformctl.py](../../deploy/spark/operations/platformctl.py) 第 225–250 行。
项目停止、另一监听器占用 Web 端口时，可能先启动 core/radio，之后才发现 Web 未就绪。
令 `listening=True` 的 mock 记录到三次变更、零次监听检查。新增的 N2 门槛没有修复
早期 readiness 已记录的问题；本次没有认定现场当前监听器存在冲突。

应在变更前检查端口和资源归属，覆盖外部 IPv4/IPv6 监听器、冲突时零变更，以及自有
健康服务的幂等启动。实现时一并核对 Jetson 对应入口的边界。

### P2 — Spark 诊断脱敏遗漏观测值

调用路径：`Collector.host → snapshot → diagnostics → redacted_diagnostics`，
位置为 [web.py](../../apps/spark-console/backend/aoc_spark/web.py) 第 25–43 行。
过滤只比较字典键，而实际观测以 `name=b210_serial`、内容放在 `value` 的结构表示。
合成序列号和 PID 在导出后仍保留，`details.InvocationID` 也绕过 `invocation_id`
匹配。这是导出逻辑缺陷，不表示本次审阅发现凭据已经泄露。

应按观测语义脱敏并归一化字段名，使用合成数据覆盖顶层 observations、组件嵌套
metrics 和 systemd details。

### P2 — 一个空闲 UE 会掩盖总无线吞吐

调用路径：`SchedulerFeed.receive → parse_ocudu → Collector.collect → UI`，
位置为 [telemetry.py](../../apps/spark-console/backend/aoc_spark/telemetry.py)
第 52–77 行。明确零传输块的 UE 被赋予空速率，汇总又要求所有 UE 的值均非空。
合成的下行 23 Mbps、上行 5 Mbps 活跃 UE 与一个空闲 UE 共存时，总吞吐变成不可用。
合成空闲 UE 在两个方向均明确报告速率为零，且 OK/NOK 传输块计数均为零。

应区分明确无流量与遥测缺失，不能仅凭零传输块计数把缺失的速率改成零。
测试覆盖全空闲、一忙一闲、两台活跃和字段确实缺失。
没有传输块时，BLER/MCS 仍应保留不可用语义。

### P2 — Active 设备视图计入 inactive 或 unknown PDU

调用路径：`Open5GS.parse_info → fresh_snapshot → Overview/Devices 筛选`，
位置为 [OverviewPage.tsx](../../apps/spark-console/frontend/src/pages/OverviewPage.tsx)
第 98–104 行和 [DevicesPage.tsx](../../apps/spark-console/frontend/src/pages/DevicesPage.tsx)
第 78–84 行。两处仅要求会话证据质量 `status=ok`，忽略 `session.state`。
合成 inactive/unknown 会话时，后端 `active_pdu_count=0`，前端 Active 条件却成立。

应共用包含活动会话状态和新鲜度的定义，覆盖 active、inactive、unknown 和过期证据，
同时保留活动 PDU 与已验证端到端连接的区别。

### P2 — Jetson 任务暂停或仅创建后，后台观测停止

调用路径：`create → current → manual execute → paused → serve`，位置为
[agent.py](../../apps/jetson-console/backend/aoc_jetson/agent.py) 第 607–609 行。
仅终态任务清空 `current`，后台采样又要求不存在 current。手动任务第一步后暂停，
阻止新采样，合成状态在 21 秒后变为过期、未连接，SSE 仍发送缓存。已创建但未运行
的 ready 任务也满足同样条件。

应区分任务预留与正在执行模组操作，验证 ready/paused 时持续只读观测，同时防止
串口并发和手动任务期间的自动恢复。

## 发布与验收缺口

- **条件性回滚风险：** 安装覆盖 systemd 单元，但
  [manage.py](../../deploy/jetson/manage.py) 第 371–374 行的回滚只切换发布并启动 Web。
  以后修改单元会留下旧代码配新单元。当前历史单元未变化，因此不能称为已发生的
  版本间回滚故障。需测试两套不同单元版本，并在回滚中恢复单元和执行 daemon-reload。
- **订阅恢复证据：** `sync-subscriptions.apply` 涵盖备份、临时 Mongo 启动、顺序插入、
  回读和清理。现有测试覆盖 helper，未覆盖整段失败编排。应使用合成数据测试部分
  插入、确认丢失、磁盘满和清理失败，再恢复备份到独立卷。此前真实导入未认证数据库
  恢复能力。本轮未在只插入决策和 BSON Int64 SQN 保留逻辑中确认新缺陷。
- **管理链路前置条件：** `inspect_management` 现在要求优先的 Wi-Fi IPv4 默认路由和
  overlay 路由，但仍未检查带路由标记的隧道实际传输路径。破坏性模组/故障测试前应
  独立核实，本轮只读检查尚未证明该路径。

## 开发顺序

先通过隔离回归测试处理三个 P1 失败路径，再修正导出脱敏、双 UE 遥测/状态语义和
暂停任务观测。发布前补上单元变化时的回滚，构建来源干净的 ARM64 包并运行手动
Python/浏览器矩阵。随后让两台 Jetson 分别覆盖 P3-15、P3-16、P3-17 和 R06：
故障矩阵、安装/回滚/重装、管理连接保留，以及完整五次启停/重新接入和单控制者检查。
证据齐备后再判断 P3-GATE。继续扩展订阅维护前应完成订阅备份恢复验证。

[路线图](../roadmap.md)仍是唯一完成清单。部署记录中较晚的启用操作覆盖当天较早的
停止状态快照，历史验收记录保持原样。

## 验证与限制

`make ci VENV=local/bootstrap-check` 通过：Jetson 72 项，Spark 53 项中一项为已有
macOS peer-credential 跳过，共享协议栈 150 项，合计 **274 项通过、1 项跳过**。
两套前端的锁定依赖安装、生产构建、TypeScript，以及文档、发布边界、许可证和
Shell 审计均通过。两个前端仍有大于 500 kB 的现有 bundle 警告。

较早的沙箱内 `make check` 因共享 HTTP 测试不能绑定 localhost 中断；获得回环端口
权限后，该目标与完整 `make ci` 均通过，未修改测试。本地为 Python 3.11.15、
Node 24.14.0，未复现 CI 的 Python 3.12 / Node 22 组合。默认 `.venv` 为不适用的
Python 3.9.6；本地检查可使用现有 `local/bootstrap-check`，或新建受支持环境。
本轮未执行目标 Python 3.10/3.12 矩阵和浏览器 E2E。

本轮仅修改中英文报告、文档导航和路线图的当前状态文字。未修复应用、部署、执行
实机回滚或关闭 Gate。文档修改完成后另行运行文档审计和空白检查。
