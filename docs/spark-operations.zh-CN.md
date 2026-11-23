# Spark Platform 运维

## 整套系统一键启停

使用已完成配置的 SSH 用户在设备本地执行：

```sh
~/aoc-ops/spark/start.sh
~/aoc-ops/spark/stop.sh
/usr/bin/python3 -I ~/aoc-ops/spark/platformctl.py status
```

这些入口同时控制 Open5GS、OCUDU gNB 和三个监测服务。启动顺序为核心网、无线、监测；
停止顺序为无线、核心网、监测，以保留停止过程的观测。只检查固定的 `aoc-v2-*` 栈服务
和 `aoc-v2-open5gs` 项目预期的 12 个容器服务。所有变更均调用既有非交互
`aoc-maintain` 动作（`status`、`verify`、`install`、`rollback`、`start`、`stop`、
`radio-*`、`core-*`、`connectivity-upgrade`），不直接执行 Docker 写操作；保留其他
容器和持久化数据。

启动在变更服务前使用 `ss --cgroup` 检查 8877 端口的 IPv4 和 IPv6 监听器。
仅当全部监听器属于正在运行的 Web 单元的 systemd 控制组，且其健康接口返回 OK，
才允许端口已占用的情况。外部或无法确认的归属、检查失败或现有 Web 不健康均在
任何变更前终止启动。这依赖内核/iproute2 的 cgroup 报告能力，不会预留端口来阻止
稍后的并发管理员操作。

启动要求 12 个核心网容器健康、gNB 通过现有 systemd 启动检查后 active，Open5GS
infoAPI 返回 N2 NG Setup 成功，以及监测／采集器健康；这些条件不证明 UE 已接入。
已运行组件只检查、不重启，缺失阶段按依赖顺序补齐。已运行但不健康的核心网，或部分运行
的核心网容器会报错，不隐式重启修复。启动失败保留已完成阶段；停止失败不再关闭其依赖或
监测平台，残留容器或进程不能报告为成功停止。

每次 helper 调用最多 330 秒，每次健康等待最多 60 秒。不自动重试写操作或回滚。超时或
中断后先查询状态，因为 systemd 任务可能仍在运行。同一用户的脚本副本共用操作锁，
但不能锁住全部网页／管理员入口，因此操作期间不要混用；维护工具自身检查继续生效。
退出码：成功 0、执行／验证失败 1、参数错误 2、脚本忙 3。成功的 `status` 查询返回 0，
即使整套系统已停止。运行输出使用英文。

脚本依赖系统 Python、systemd 工具、`ss`、Docker 只读访问能力和既有受限维护权限。
先备份已有目标目录，再从仓库安装或通过 SSH 传输相同文件：

```sh
mkdir -p ~/aoc-ops/spark
install -m 0755 deploy/spark/operations/start.sh deploy/spark/operations/stop.sh \
  deploy/spark/operations/platformctl.py ~/aoc-ops/spark/
```

执行前核对传输哈希。设备不需要完整仓库或虚拟环境。脚本独立于应用发布包交付，撤回
时恢复其备份，不回滚应用；不开启开机自启，不包含设备连接地址。
启停及对齐检查记录见
[2026-09-24 启停验收](acceptance/2026-09-24-platform-lifecycle.zh-CN.md)和
[2026-11-23 对齐验收](acceptance/2026-11-23-spark-ue-alignment.zh-CN.md)。

## 平台生命周期

仅维护监测应用时，操作 `aoc-observe.service`、`aoc-monitor-web.service` 和
`aoc-control.service` 这三个服务。停止监测应用不得改变无线栈和核心网服务。健康检查：

```sh
curl -fsS http://127.0.0.1:8877/api/v1/health
```

浏览器通过 SSH 隧道访问，监听地址保持为回环地址。

## 监测、遥测与网桥计数

平台展示主机、B210、gNB、N2、核心网功能、接口、设备、会话和事件。数值必须带
来源时间与证据质量；SSE 中断后实时值变为 stale 或 unknown。N3、N6 与 bridge
计数器分别展示；能读取计数器不代表近期有流量，也不代表端到端路径已经验收。

- **OCUDU JSON 指标（`127.0.0.1:8879`）**：`aoc-observe.service` 通过 WebSocket
  连接 `ws://127.0.0.1:8879`（已由 `8001` 迁出，以避开共驻 vLLM 容器）。
  `aoc-v2-metrics-guard.service`（`RemainAfterExit=yes`）挂载 `table inet aoc_v2_metrics_guard`
  拒绝非 root 访问 `8879`。使用 `scripts/spark/enable_radio_json_metrics.py` 迁移或回滚时，
  `remove_guard()` 会在删除 nftables 表前显式停止 `aoc-v2-metrics-guard.service`，确保后续
  启动无线时能重新执行守护规则。
- **动态 Docker 网桥发现**：`collector.py::bridge_interface()` 通过 `docker network inspect`
  动态获取 `aoc-v2-open5gs-core` 的真实网桥名（如 `br-<id12>`），不再依赖静态接口名硬编码。

健康的 SSE 连接持续保持，每次发布快照前检查会话。Web 进程保留 10 秒优雅关闭
限制，不应再每 15 秒主动轮换连接。反复出现断连提示时，应结合服务重启次数、
隧道健康和采集时间戳排查。

Devices 页面只有在存在明确证据时才合并身份。无法确定时，RNTI 上下文与订阅会话
保持分离。Operations 页面在刷新后仍能展示任务步骤、失败、清理和审计记录。
执行器流在返回终态前断开时，API 查询原任务，不重发操作。任务未知或执行器不可用
时记录为 interrupted，并释放 API 的任务预留；再次操作前应检查服务状态，因为原操作
可能已经执行。

## 协议栈生命周期

使用 `aoc-v2ctl preflight`、`prepare`、`start`、`status` 和 `stop` 管理本项目的
OCUDU/Open5GS 栈。启动要求核心网就绪、B210 无冲突、gNB 进程稳定、
`aoc-v2-cpu-latency.service`（`PartOf=aoc-v2-radio.service`）运行且 N2 建立。
停止遇到异常容器或服务退出时会保留诊断所需资源并记录原因。持久化的射频调优参数
（`rx_gain=54`、`pusch.max_ue_mcs=24`）应落在 `runtime.py` 中，避免依赖 `/run/systemd/system/`
临时 drop-in；在存在共驻负载的主机上保留 `realtime.conf`（`CPUAffinity`、`LimitRTPRIO=99`）。

射频修改必须一次只变更一个变量，保存备份，并在相同条件下重新执行 UE benchmark
和 Spark evidence report。

## 升级与回滚

监测平台可在协议栈运行时升级。只停止三个平台单元，校验并安装发布，再启动并检查
健康与 SSE。回滚必须恢复上一发布和数据库备份，不能改变无线栈或核心网服务。若同步升级了
无线指标端口配置，重启无线服务后应同时重启 `aoc-observe.service`，让 `SchedulerFeed` 重新建立
与 `127.0.0.1:8879` 的连接。

数据库 schema 6 为历史菜单建立保留指标名索引。安装器在 Web 启动前备份并迁移
已有数据；首次补建需要时间，后续菜单查询使用索引。降级需恢复配套数据库备份，
旧代码不能打开 schema 6。

从本轮生命周期改进开始，完整启动还须通过 Open5GS infoAPI 确认 N2 NG Setup。
状态分别显示核心网健康、无线进程和 N2 建链；单独 gNB active 不代表协议栈就绪，
也不证明 UE 已接入或数据可用。N2 等待失败时保留已启动服务供检查，不启动后续阶段。
