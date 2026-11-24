# Spark Platform 运维指南

[English](spark-operations.md)

本指南介绍 **DGX Spark** 上 Spark Platform Web 控制台日常使用、整套启停运维、
观测语义及独立升级/回滚流程。

## Web 控制台导览

Spark Platform 仅监听 `127.0.0.1:8877`，从工作站通过 SSH 端口转发访问
（`ssh -L 8877:127.0.0.1:8877 <user>@<spark-host>`）：

<!-- ASSET_SLOT: docs/assets/screenshots/spark-console-overview.png | 16:9 脱敏后的 Spark Platform Overview / Devices 页面截图（须遮蔽 IMSI、主机名与 Tailnet IP） -->

| 页面 | 路由 | 观测与管控能力 |
| --- | --- | --- |
| Overview | `/` | 系统健康总览、证据新鲜度、RAN/核心网状态与在线 UE 数 |
| gNB | `/gnb` | OCUDU 进程代次、USRP B210 状态、射频基线与 `8879` 实时调度指标 |
| Core Network | `/core` | Open5GS 12 容器状态、N2 NG Setup 就绪度与 N3/N6/网桥计数 |
| Devices | `/devices` | 按明确证据关联的 RNTI 上下文与活动 PDU 会话（`/devices/{id}` 查看单台详情） |
| Events | `/events` | 可筛选无线、核心网与采集器事件时间线 |
| Metric history | `/history` | 持久化时序 KPI 历史曲线 |
| Operations | `/operations` | 受限协议栈/服务控制任务、分步执行状态、取消与审计日志 |
| Diagnostics | `/diagnostics` | 子系统探测、采集时间戳与接口诊断明细 |

完整的 REST 与 SSE 接口说明见[REST 与 SSE 接口参考](reference/api-reference.zh-CN.md#spark-platform-接口1270018877)。

## 整套系统一键启停

安装 `aoc-maintain` 批准包并将 `deploy/spark/operations/{start.sh,stop.sh,platformctl.py}`
复制到 `~/aoc-ops/spark/` 后，可执行一键生命周期控制：

```sh
~/aoc-ops/spark/start.sh
~/aoc-ops/spark/stop.sh
/usr/bin/python3 -I ~/aoc-ops/spark/platformctl.py status
```

- **启动顺序**：`core`（12 个容器健康）-> `radio`（B210 就绪、`aoc-v2-cpu-latency.service` 运行且 N2 NG Setup 成功）-> `monitor`（`aoc-control`、`aoc-observe`、`aoc-monitor-web`）。已健康阶段保持不重启。
- **停止顺序**：`radio` -> `core` -> `monitor`，在停机期间保留观测日志并安全保留 MongoDB 数据卷。
- **前置检查与互斥**：启动前会核验 `8877` 端口进程归属；每次仅使用单一操作入口（`platformctl.py`、`aoc-v2ctl` 或 Web Operations），避免并发冲突。

Helper 超时、退出码与端口守护策略见[端口与运行时参考](reference/ports-and-runtime.zh-CN.md)。

## 平台单独维护与协议栈直接控制

- **仅维护监测平台**：可独立操作 `aoc-observe.service`、`aoc-monitor-web.service` 与
  `aoc-control.service` 而不中断 5G 无线与核心网。健康探活：
  ```sh
  curl -fsS http://127.0.0.1:8877/api/v1/health
  ```
- **直接控制协议栈（`aoc-v2ctl`）**：管理员可通过 `preflight`、`prepare`、`start`、
  `status` 与 `stop` 管理 OCUDU/Open5GS。持久化射频调优集中放在 `deploy/spark/stack/runtime.py`；
  调整射频参数时一次仅改一个变量并留存备份。
- **实时流与任务断点续查**：SSE 连接在健康状态下保持长连接；若执行器流在任务终态前
  断开，API 会直接查询原任务结果而非重发动作。遇到超时或中断先查 `status` 再决定下一步。

## 独立升级与回滚

Spark Platform 可在 5G 协议栈持续运行期间单独升级或回滚：

1. 仅停止三项平台服务（`aoc-control`、`aoc-observe`、`aoc-monitor-web`）。
2. 校验并安装新版本发布包（`install.py verify` -> `check-host` -> `install`，或使用 `aoc-maintain install`）。
3. 启动平台服务并验证 `/api/v1/health` 与 SSE 实时更新。
4. 若同步升级了无线配置或 `enable_radio_json_metrics.py`，重启无线后请同步重启 `aoc-observe.service`，使其重新接入刷新后的指标端口。

回滚时同步恢复上一版本程序与对应升级前数据库备份，不改动 OCUDU 或 Open5GS 运行状态。
