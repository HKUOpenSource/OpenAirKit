# 下一轮开发审阅 — 2026-09-28

[English](2026-09-28-next-round-review.md)

后续进展：[本地修复与验证](2026-09-28-review-fixes.zh-CN.md)。
下文保留修复前的审阅结论；实机验收仍待后续进行。

审阅版本：`5f2d06f9baa586fb1bff73ac9c7c0822d2d62b87`，开始时为干净的 `main`。
范围包括两个应用、共享 UI、协议栈与部署工具、现行文档、本地测试和用户提供的
三台设备。仓库没有 `.codegraph/` 索引，因此采用源码检查和隔离复现。

本次问题是：下一轮开发可以依赖哪些基线？应用正常运行，但实机 5G 协议栈目前
停止。检查发现若干发布前必须处理的缺口，本记录不关闭任何[路线图](../roadmap.md)门槛。

## 二次复核结论

按用户要求质疑原结论后，补做正常生命周期模拟器、真实 Spark 协议处理线程并发实验，
并检查固定版本上游源码。上一轮定性过于一概而论：**四项代码缺陷确认，一项调整为
P2 部署工程缺口，一项改为设计问题，不再列为确定缺陷。当前没有 P1。**

| 原发现 | 复核判定 | 依据 |
| --- | --- | --- |
| 协议栈重建链 | P1 降为 P2 工程缺口 | 应用包 staging/verify、Open5GS 生成均正常；缺的是项目自有生命周期安装输入。 |
| Jetson 取消后采样失败 | 保留 P2，收窄范围 | 正常后台探测持续失败；不带 probe 的采样仍可成功。 |
| Jetson ready/paused 停采 | 撤回“确定 P2” | 代码明确做任务级互斥，过期降级正确，文档未承诺任务等待期间持续观测。 |
| Spark 并发取消 | 保留 P2 | 真实协议线程可复现文件竞争和任务残留，不依赖伪造异常。 |
| 诊断脱敏 | 保留 P2 | 既有导出契约明确要求移除这些标识；不是凭据泄漏或鉴权绕过。 |
| 空闲 UE 吞吐 | 保留 P2 | 固定上游中零速率是有效值，适配器抹去它并使合计失效。 |

Spark parity 当前失败属于测试预期陈旧，不能据此认定导航产品错误；八项导航是已记录的预期设计。

## 当前设备基线

设备观察时间为 9 月 28 日香港时间约 09:15。Jetson A、B 分别指用户提供的第一、
第二台 Jetson。SSH 检查读取选定的服务属性、回环健康接口、项目容器状态、USB
产品 ID 和发布哈希。Jetson `ue-status` 使用现有受限维护 helper，包含其正常锁与
审计记账。本次没有启停服务、部署、写模组、改路由或发起新的 UE 数据探测。

| 证据 | Spark | Jetson A | Jetson B |
| --- | --- | --- | --- |
| SSH / 架构 | 可达 / ARM64 | 可达 / ARM64 | 可达 / ARM64 |
| 系统 / Python | Ubuntu 24.04.4 / 3.12.3 | Ubuntu 22.04.5 / 3.10.12 | Ubuntu 22.04.5 / 3.10.12 |
| 应用版本 | 0.2.0 | 0.6.0 | 0.6.0 |
| 发布 ID | `a4f6b8caf8f015af` | `9ed9fbcf1d68bf78` | `9ed9fbcf1d68bf78` |
| 清单文件哈希匹配 | 28/28 | 51/51 | 51/51 |
| 应用服务 | 三项均 active/running | Device、Web 均 active/running | Device、Web 均 active/running |
| 应用自动重启计数 | 全部为零 | 均为零 | 均为零 |
| 公开健康接口 | OK，collector OK | OK，设备证据 OK | OK，设备证据 OK |
| USB 产品存在 | B210 | RM520N-GL | RM520N-GL |
| 新鲜注册 / connected | 未独立关联 | False / false | False / false |
| 上报 data PDU active | — | True | False |
| 管理保护 / 恢复暂停 | — | True / true | True / true |

Spark 的 `aoc-v2-core.service`、`aoc-v2-radio.service` 均为 inactive/dead。
按 `aoc-v2-open5gs` 项目查询容器，包括停止容器，结果为空；有界 N2 HTTP 检查失败。
两台 Jetson 均报告无线、注册及数据路径失败。Jetson A 保留的 active-PDU 标志不能
证明连接。本次没有确认协议栈停止的原因或时间，也没有重新启动它。

本次观察更新了[9 月 27 日审阅](2026-09-27-next-round-review.zh-CN.md)中的运行基线；
[后续部署记录](2026-09-27-ui-deployment.zh-CN.md)仍保留为历史验收证据。
应用健康表示服务或证据可用，不能据此认定 5G 已连接。

Jetson A 另有两项旧的非 V2 服务处于 failed，均已禁用；仅凭这一点不能认定存在
另一个模组控制进程。Spark 上检查到的另一平台服务均停止，但其核心网和监控服务
仍设置为开机启用。本项目应用服务 disabled，核心网与无线服务 static；重启恢复
及资源归属尚未验收。管理保护来自应用上报，本次没有独立验证实际隧道承载和策略路由。

三个应用清单仍记录 `dirty=true`，源码基点为 `87e059f`。文件匹配只证明与这些清单
一致，不证明与当前干净提交完全等价。清单 SHA-256：

- Spark：`9c7bd2ce1425a0d52b11d632b5f7ac6fc374cf444a73996a23e17797e98036bf`。
- 两台 Jetson：`004ce1c7a84910237ad06876ec199133118dbc761b9bdeaeba8087aef1cf87a0`。

## 问题、限定条件与回归要求

### P2 — 项目协议栈生命周期源码及安装输入不完整

`python scripts/aocctl --help` 在参数解析前即报
`ModuleNotFoundError: No module named 'scripts.v2.runtime'`。
[scripts/aocctl](../../scripts/aocctl) 第 6 行导入了缺失实现。应用调用路径为
Web → executor → [control.run_step](../../apps/spark-console/backend/aoc_spark/control.py)
第 36–45 行 → 已安装的 `/usr/local/bin/aoc-v2ctl`。生命周期控制器需要 V2 core/radio
unit，但当前源码树没有对应定义；`scripts/install_radio.py`（审阅时路径，随后归档）
第 21 行仍安装旧 `aoc-stack`、`aoc-core`、`aoc-gnb`，并要求历史 launcher。

现行 [Spark 安装指南](../setup-bs-spark.md)第 10–12、37 行仍引导使用旧镜像锁与
协议栈模板，其中包含 OAI/MySQL/IMS；Open5GS 的实际锁位于 `stacks/open5gs`。

反证限制了影响范围：`scripts/aocctl` 不参与现行应用打包。在临时目录执行
`monitor_release.stage + verify` 成功，得到 28 个文件及发布 ID `a4f6b8caf8f015af`；
Open5GS `render()` 也成功，OCUDU 二进制构建入口仍存在。应用与协议栈分离是有意设计；
已安装的独立启停脚本通过维护 helper 操作已有 V2 unit，不调用这个损坏的仓库入口。

仍存在的缺口是：无法从现行输入完整追溯项目自有生命周期控制器与 unit 的干净安装，
或审阅其更新。正式运维指南和 Web executor 仍要求已安装的 V2 CLI，但当前没有对应
实现、unit 生成器或已声明的外部获取包。这属于 P2 可重现部署缺口，不能说应用构建
失败或现网控制器故障。应补齐受支持的项目生命周期路径并归档旧工具，不能简单改用
旧 `scripts.aoclib.cli`；针对实际受支持入口增加 CLI help、安装完整性与无 RF 服务演练。

### P2 — 取消 ready/paused Jetson 任务后，后续采样持续失败

调用路径：Cancel → `cancel_job` → `sample(True)` → `check_cancel`。
[agent.py](../../apps/jetson-console/backend/aoc_jetson/agent.py)第 453–460 行设置
取消事件后，在没有活动 worker 时直接结束任务，却没有清除事件；第 441–446 行
的清理只由 `execute` 执行。ready、paused 两种任务均复现连续采样 unavailable，
原因是 `Cancelled at a safe operation boundary`。二次复核运行两个真实模拟器进程，
经鉴权 FastAPI、Unix RPC 和正常 serve 循环，不改 cached 状态或时钟。取消后 12 秒、
24 秒及维护模式开→关后仍失败，证据时间持续推进，排除了只读到旧缓存的可能。
一个实例重启后恢复，另一个新建并完成任务后恢复。
准确范围是网络质量允许进入探测分支时的 `sample(True)`；`sample(False)` 仍可成功。
不能说所有 AT 查询都会失败，但正常健康网络下的后台轮询确实受影响。
回归应检查取消后保持空闲时的连续采样与 SSE 证据推进，不创建替代任务。
现有浏览器测试取消后立即创建 Recover，恰好掩盖了该问题。

### 设计待定 — Jetson 在整个任务期间暂停后台观测

调用路径：`create` → ready，或 `execute` → paused → `serve`。
[agent.py](../../apps/jetson-console/backend/aoc_jetson/agent.py)第 607 行用
`not self.current` 控制全部后台采样；ready、paused 即使没有执行中的 worker，仍保留
`current`。两个真实模拟器经正常 API 流程等待 23 秒，没有调整时钟或缓存，均确认
证据时间不推进且质量变为 stale。

但仅凭这个行为不足以判定代码错误：20 秒后撤销 connected 是正确的过期保护，
代码有意按整个任务互斥，现行文档也未承诺预约计划期间持续观测。因此撤回原来的
“确定 P2”定性。应先明确产品期望：接受任务级独占时解释暂停原因，或要求等待确认时
继续观测。只有选择后者才修改调度，并验证硬件锁、无并发串口访问及手动期间无自动恢复。

### P2 — Spark 并发取消可能使操作一直被占用

调用路径：`ControlHandler` 多线程 → `execute` / `request_cancel` → `persist`。
[control.py](../../apps/spark-console/backend/aoc_spark/control.py)第 68–78 行共用
同一个任务临时文件，但 `emit` 不持有第 119–128 行取消操作所用的锁。
确定调度的双线程复现中，取消先替换临时文件，执行线程首次 emit 随后抛出
`FileNotFoundError`；第 90 行还位于 try 外。没有实际命令执行，worker 已退出，
任务仍为 `cancel_requested`，下一项操作被 `operation_in_progress` 拒绝，Web
恢复轮询一直看到非终态。准确说是当前 executor 进程内持续残留，直至外部恢复，
并非不可修复的永久锁死。

二次复核使用 socketpair 上的真实 `ControlServer` 多线程 handler，仅替换 macOS
缺少的 Linux peer-credential 查询。后续三次真实协议 query 仍为 `cancel_requested`，
新 run 返回 conflict。UI 允许取消 queued 任务，Web 也不等待执行完毕才返回，路径确实
可达。另做 100 次无持久化补丁、无调度 barrier 的并发：6 次遗留任务且 run 报错，
16 次 cancel handler 报错，78 次因竞争被标为 failed。这只是人工并发可触发证据，
不能解释为生产发生概率。
应串行化状态更新和持久化，保护首次发送；回归同时运行
取消与进度线程，断言任务终结且下一项操作能够提交。

### P2 — Spark 诊断脱敏遗漏 observation 的值

调用路径：Diagnostics → `/api/v1/diagnostics` → `redacted_diagnostics(snapshot())`。
[web.py](../../apps/spark-console/backend/aoc_spark/web.py)第 33–43 行只过滤字典键；
collector 把 `b210_serial`、`radio_pid`、`b210_holder_pids` 放在 `name`，内容位于
`value`，因此原样导出。`InvocationID` 与过滤项 `invocation_id` 也不匹配。
二次复核通过真实登录和鉴权后的诊断接口，确认四类合成标识残留，普通 `pid` 键则正确
脱敏。早于本次审阅的[页面验收契约](2026-09-12-v2-p2-07-pages.md)第 17 行明确要求
移除 PID、InvocationID 与 B210 序列号，因此确属导出承诺失效；正常登录页面显示
这些信息本身不是问题，也没有证据表明密码、SIM 密钥泄露或鉴权绕过。
应规范化字段名并识别 observation，在完整导出 JSON 中断言
敏感哨兵值不存在。本次没有导出真实诊断，也未进行凭据泄露测试。

### P2 — 一个空闲 UE 会使总无线吞吐变成不可用

调用路径：scheduler → `parse_ocudu` → collector → gNB 图表。
[telemetry.py](../../apps/spark-console/backend/aoc_spark/telemetry.py)第 52–53 行
在传输块为零时把明确的零 bitrate 改为 null，第 73–77 行又要求所有 UE 的 bitrate
均非 null。合成活动 UE 单独显示下行 23 Mbps、上行 5 Mbps；加入明确上报零 bitrate
及零传输块的空闲 UE 后，两项总量均变成 unavailable。应保留明确零流量，并对缺失
bitrate、MCS、BLER 保留 unavailable 语义；分别覆盖活动/空闲组合和真正缺失字段。

反证：`test_scheduler_units_unknown_cqi_no_blocks_and_epoch` 已明确断言无传输块时
bitrate 不可用，说明这是有意写下的逻辑。但该 fixture 是正的上行速率配零上行块，
并未覆盖有效的空闲零速率。仓库固定上游提交的
[scheduler 计算](https://gitlab.com/ocudu/ocudu/-/blob/050a2bb72e1d794cd60570d809987c1fcda3e54b/lib/scheduler/logging/scheduler_metrics_handler.cpp#L601)
以传输位数除以报告时长，无字节时得到零；
[cell consumer](https://gitlab.com/ocudu/ocudu/-/blob/050a2bb72e1d794cd60570d809987c1fcda3e54b/apps/units/flexible_o_du/o_du_high/du_high/metrics/consumers/scheduler_metrics_consumers.cpp#L171)
对包含零值的 UE 速率直接求和。本地复核分别覆盖单活动、活动加明确零、缺失速率、
纯空闲、零速率但有失败块；只有真正缺失速率才应使完整总量不可知。因此保留为
数据语义缺陷，不应说成无线故障或实际业务吞吐中断。

## 验证与发布缺口

本地使用已有 `local/bootstrap-check`，Python 3.11.15、Node 24.14.0。
默认 `.venv` 是不受支持的 Python 3.9.6。本地结果不代替 Python 3.10/3.12 与
Node 22 的发布矩阵。

- `make check VENV=local/bootstrap-check`：Jetson 79 项通过，Spark 64 项通过、
  1 项 macOS peer-credential 跳过。共享测试最初因沙箱禁止本机绑定端口失败；
  获得 loopback 权限后，`make test-stack` 全部 156 项通过。
- 余下 `make check` 目标单独运行通过：两端 TypeScript、文档、发布边界、许可证与
  shell 审计。Python 合计 **299 项通过、1 项跳过**；前端行为测试 7 项全部通过。
- 使用已安装依赖的两端生产构建均通过，保留原有超过 500 kB 的 chunk 警告。
  本次未重新安装依赖，也未构建 ARM64 发布包。
- `make e2e-jetson VENV=local/bootstrap-check` 在隔离模拟器上通过，包括 35 秒
  持续流和桌面/移动流程。
- `make e2e-spark VENV=local/bootstrap-check`：`browser.mjs`、`information.mjs`
  通过；`parity.mjs` 第 298 行仍预期五项导航，当前设计已有八项，断言失败。
  应更新陈旧断言并跑完整套件；本次没有认证其后的 parity 断言。
- 订阅维护仍缺完整 apply/失败/恢复覆盖：部分插入、响应丢失、磁盘满、cleanup
  失败和向独立测试卷恢复备份，均需用合成数据验证。

上一轮 CFUN 恢复、Web 控制 EOF 对账、Spark listener 预检、活动会话过滤、历史索引
和 SSE 生命周期修复已在当前代码中。Jetson 回滚恢复 unit 的源码修复也已存在，
实机回滚仍需另行验收。不能把这些源码问题继续当作未修复项，也不能据此关闭硬件门槛。

## 下一轮开发顺序

1. 补齐可重建的协议栈控制/安装链并修正安装文档；使完整浏览器基线通过，包括 Spark parity。
2. 为 Jetson 取消标记残留及 Spark 并发取消补回归并修复，再修正诊断脱敏与空闲 UE 吞吐语义。
   ready/paused 期间的观测要求单独明确后，再决定是否调整任务互斥。
3. 从干净提交构建可追溯 ARM64 应用包，运行目标 Python 矩阵；扩展维护能力前补订阅失败/恢复测试。
4. 确认独立管理通道与资源归属，再明确安排实机协议栈恢复及验收。完成 P3-15 故障矩阵、
   两台 Jetson 的 P3-16 安装—回滚—重装、两个平台 ARM64 发布各自的 R06 验收，
   以及 P3-17 五次启停/重新接入、单模组控制者验证；证据齐全后再评估 P3-GATE。

路线图继续作为唯一完成清单。本次只新增中英文审阅记录、更新文档导航和当前状态说明；
没有应用修复、部署、重启、回滚或新门槛完成。设备地址、凭据、订阅身份及原始运行输出均未写入。
