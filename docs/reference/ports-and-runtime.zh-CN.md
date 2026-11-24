# 端口分配、路由策略与运行时参数参考

[English](ports-and-runtime.md)

本文档集中定义回环服务端口分配、实时性与硬件互斥保护、Jetson 路由与自愈阈值以及
生命周期脚本的超时与退出码契约。

## 回环服务与端口分配

所有 Web 控制台与指标服务仅绑定回环地址（`127.0.0.1`），远程访问统一通过 SSH 端口转发（`ssh -L ...`）。

| 监听端点 | 归属服务 | 访问策略与隔离说明 |
| --- | --- | --- |
| `127.0.0.1:8877` | Spark Platform（`aoc-monitor-web.service`） | 鉴权 Astryx Web 控制台、REST API 与 SSE 流（`/api/v1/stream`） |
| `127.0.0.1:8878` | Jetson Console（`aoc-v2-jetson-web.service`） | 鉴权 Astryx Web 控制台、REST API 与 SSE 流（`/api/v1/events/stream`） |
| `127.0.0.1:8879` | OCUDU gNB JSON 指标（`ws://127.0.0.1:8879`） | 由 `aoc-v2-metrics-guard.service` 保护，仅允许本机 root（`aoc-observe.service`）连接 |
| `127.0.0.1:8000–8002` | **DGX Spark** 上保留空闲 | 5G 协议栈不占用此端口段，供共驻 AI 推理容器（如 vLLM）无冲突使用 |

## 实时性与硬件资源隔离机制

| 适用主机 | 机制 / 单元 | 作用说明 |
| --- | --- | --- |
| Spark 基站侧 | `aoc-v2-cpu-latency.service`（`PartOf=aoc-v2-radio.service`） | gNB 运行期间锁定 `/dev/cpu_dma_latency=0`，避免 CPU 进入深度休眠 |
| Spark 基站侧（可选） | `deploy/spark/stack/systemd/aoc-v2-radio.service.d/realtime.conf.example` | 提供 `CPUAffinity` 与 `LimitRTPRIO=99` drop-in 模板，隔离 gNB 实时线程与共驻 AI 负载 |
| Jetson UE 侧 | `/var/lib/agentic-ocudu/v2-ue/serial.lock` | `aoc-v2-jetson-device.service` 持有的 AT 串口排他锁 |
| Jetson 开机协调（可选） | `/opt/agentic-ocudu/jetson/boot_connect.py` + `aoc-v2-jetson-boot.service` | 校验 `/etc/aoc-v2-jetson/boot.json` 摘要，等待 USB/Wi-Fi/`tailscale0` 就绪后每个内核 `boot_id` 至多执行一次标准入网，并将脱敏状态写入 `/var/lib/aoc-v2-jetson-boot/public/status.json` |

## Jetson 路由切换与自愈策略参数

| 参数项 | 阈值与行为规则 |
| --- | --- |
| 自有默认路由 | 内核协议号 `186`：`metric 5` = Wi-Fi 管理兜底路由；`metric 10` = 蜂窝数据优先路由 |
| 外部默认路由要求 | 所有管理员或 NetworkManager 创建的默认路由 metric 须严格大于 `10` |
| 绑定接口诊断路由 | 到 UPF、`ext-DN` 与公网探测目标的主机路由始终绑定蜂窝接口，便于在 Wi-Fi 回退期间持续检测恢复 |
| 探测频率与过期阈值 | 正常采样间隔 `10 s`；证据过期上限 `20 s` |
| 切至蜂窝优先条件 | 连续 `2` 组新鲜探测（含公网目标）全部成功 |
| 回退 Wi-Fi 条件 | 连续 `2` 组探测失败、证据过期（`> 20 s`），或注册/PDU/网卡接口丢失 |
| 自动恢复配额 | 仅在用户成功执行 Setup/Recover 后启用：断网后自然等待 `120 s` -> 至多 `2` 次恢复任务（冷却期 `>= 300 s`），单任务至多重连 `1` 次 |

## 生命周期脚本超时与退出码

同时适用于 `~/aoc-ops/spark/platformctl.py` 与 `~/aoc-ops/jetson/platformctl.py`：

| 属性 | 契约说明 |
| --- | --- |
| 维护助手调用超时 | 单次 `aoc-maintain` 调用上限 `330 s` |
| 健康检查等待窗口 | 单阶段健康等待 `60 s`；Web 服务优雅关闭上限 `10 s` |
| 退出码 `0` | 操作成功（服务正常停止时查询 `status` 亦返回 `0`） |
| 退出码 `1` | 执行或状态核验失败 |
| 退出码 `2` | 命令参数无效 |
| 退出码 `3` | 用户级操作锁忙 |
