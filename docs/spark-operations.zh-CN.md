# Spark Console 运维指南

[English](spark-operations.md)

本指南说明 **DGX Spark** 上 **Spark Console** Web 控制台日常操作、全栈统一启停控制、
遥测状态语义以及平台独立升级/回滚流程。

## Web 控制台导览

Spark Console 仅监听本地回环 `127.0.0.1:8877`，从工作站通过 SSH 端口转发访问
（`ssh -L 8877:127.0.0.1:8877 <user>@<spark-host>`）：

<!-- ASSET_SLOT: docs/assets/screenshots/spark-console-overview.png | 16:9 脱敏后的 Spark Console Overview / Devices 页面截图（须遮蔽 IMSI、主机名与 Tailnet IP） -->

| 页面 | 路由 | 核心能力 |
| --- | --- | --- |
| Overview | `/` | 系统健康概览、数据时效性、RAN/核心网状态与在线 UE 数量 |
| gNB | `/gnb` | OCUDU 进程实例代次、USRP B210 状态、射频基线与 `8879` 实时调度指标 |
| Core Network | `/core` | Open5GS 12 容器状态、N2 NG Setup 就绪情况与 N3/N6/网桥计数 |
| Devices | `/devices` | 按多维证据关联的 RNTI 上下文与活动 PDU 会话（`/devices/{id}` 单台详情） |
| Events | `/events` | 可筛选的无线、核心网与采集器事件时间线 |
| Metric history | `/history` | 持久化时序 KPI 历史趋势图表 |
| Operations | `/operations` | 受限协议栈/服务控制任务、分步执行状态、取消与持久审计日志 |
| Diagnostics | `/diagnostics` | 子系统探测、采集时间戳与网桥/接口诊断明细 |

供自定义监控面板与外部 AI 客户端调用的 REST 与 SSE 接口规范，请参阅
[REST 与 SSE 接口参考](reference/api-reference.zh-CN.md#spark-console-接口1270018877)。

## 全栈统一启停控制

部署 `aoc-maintain` 批准包并将 `deploy/spark/operations/{start.sh,stop.sh,platformctl.py}`
复制到 `~/aoc-ops/spark/` 后，可执行全栈受限免密运维脚本：

```sh
~/aoc-ops/spark/start.sh
~/aoc-ops/spark/stop.sh
/usr/bin/python3 -I ~/aoc-ops/spark/platformctl.py status
```

- **启动时序**：`core`（12 个容器健康）-> `radio`（USRP B210 就绪、`aoc-v2-cpu-latency.service` 运行且 N2 NG Setup 完成）-> `monitor`（`aoc-control`、`aoc-observe`、`aoc-monitor-web`）。已处于健康状态的阶段保持运行不重启。
- **停止时序**：`radio` -> `core` -> `monitor`，在协议栈退出期间维持遥测可观测性并安全保留 MongoDB 数据卷。
- **前置检查与并发互斥**：启动前核验 `8877` 端口监听进程归属；同一时刻仅通过单一入口（`platformctl.py`、`aoc-v2ctl` 或 Web Operations）下发启停操作，避免并发冲突。

维护助手超时、退出码及端口守护规则详见[端口与运行时参考](reference/ports-and-runtime.zh-CN.md)。

## 平台单独维护与协议栈直接控制

- **仅维护监测平台**：可独立重启或检查 `aoc-observe.service`、`aoc-monitor-web.service`
  与 `aoc-control.service`，不影响 5G 无线与核心网持续服务。健康探活命令：
  ```sh
  curl -fsS http://127.0.0.1:8877/api/v1/health
  ```
- **直接控制协议栈（`aoc-v2ctl`）**：管理员可通过 `preflight`、`prepare`、`start`、
  `status` 与 `stop` 直接管理 OCUDU/Open5GS。持久化射频调优参数统一维护于
  `deploy/spark/stack/runtime.py`；修改射频参数时每次仅调整单项变量并保留基线备份。
- **SSE 长连接与任务断点续查**：SSE 连接在健康周期内持久保持；若执行器流在任务达到终态前
  断开，API 将直接查询原任务状态而非重复触发变更。遇超时或断连时请先查 `status`。

## 独立升级与回滚

Spark Console 可在 5G 协议栈不断网的情况下单独升级或回滚：

1. 仅停止三项平台服务（`aoc-control`、`aoc-observe`、`aoc-monitor-web`）。
2. 校验并安装目标版本离线包（`install.py verify` -> `check-host` -> `install`，或使用 `aoc-maintain install`）。
3. 启动三项平台服务，核验 `/api/v1/health` 与 SSE 实时推送恢复正常。
4. 若随升级同步更新了无线配置或 `enable_radio_json_metrics.py`，重启无线单元后须同步重启 `aoc-observe.service`，确保采集器重新接入刷新后的指标流。

回滚时同步恢复上一版本程序及对应升级前数据库备份，不影响 OCUDU 与 Open5GS 的运行状态。
