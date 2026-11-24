# Spark 故障排查

[English](troubleshooting-bs-spark.md)

当 **DGX Spark** 基站或核心网侧出现异常时，可按以下故障现象分段定位。

## 监测平台不可用或缺少无线指标

- **`127.0.0.1:8877` 无法访问或 SSE 断开**：检查 `aoc-control.service`、`aoc-observe.service`
  与 `aoc-monitor-web.service` 服务状态及日志。若 `/api/v1/health` 正常但 SSE 断开，
  优先排查 SSH 隧道稳定性与登录会话是否过期。
- **主机与核心网指标正常但缺少 gNB 调度指标**：
  - 执行 `ss -tna | grep :8879`，确认 `127.0.0.1:8879` 处于 `LISTEN` 且已与 `aoc-observe` 建立 `ESTAB` 连接。
  - 执行 `sudo nft -nn list table inet aoc_v2_metrics_guard` 核验 `8879` 端口防火墙规则。
  - 若网桥流量计数为空，执行 `docker network inspect aoc-v2-open5gs-core` 确认网桥接口处于活动状态。

## OCUDU 无线栈启动失败

- **进程退出或 B210 设备冲突**：运行 `aoc-v2ctl status` 并查看 `aoc-v2-radio.service` 日志，确认无其他进程占用 USRP B210。
- **进程在运行但 N2 未建链**：先核查 Open5GS AMF 容器健康状态，留存失败现场日志后再重试。
- **配置未生效**：运行 `systemctl show aoc-v2-radio.service -p DropInPaths`，排查是否存在遗留的 `/run/systemd/system/` 临时覆盖文件屏蔽了 `runtime.py` 基线设置。

## Open5GS 核心网异常

- 通过 `docker ps -a` 与 `docker logs` 检查故障容器的退出码或 OOM 事件，并对 N2、N3、N4、N6 分段排查。
- 若 `mongo` 在 Linux 7.0+ 内核因 TCMalloc `rseq` 分配异常退出，核对渲染后的 `compose.json` 是否包含 `GLIBC_TUNABLES=glibc.pthread.rseq=1`（见[硬件与 TB01 附录](reference/hardware-notes.zh-CN.md#主机系统与内核兼容性说明)）。

## UE 状态显示陈旧或离线

- 在 Spark Console 中对比当前 gNB 进程实例代次（Generation ID）、RAN 上下文时间戳、Open5GS 会话状态与 UE 端探测状态。gNB 重启前采集的会话属于历史记录，须待重启后生成新的关联证据方可恢复在线状态。

## 射频报错（`underflow` / `late`）或吞吐偏低

- 确认 `aoc-v2-cpu-latency.service` 处于 `active`；若 Spark 同时运行高负载 AI 推理任务，须按[端口与运行时参考](reference/ports-and-runtime.zh-CN.md)确认已启用 `realtime.conf` CPU 核芯隔离。
- 对照[网络契约与射频基线](reference/network-and-rf-profile.zh-CN.md)核对 B210 增益与 MCS 上限，检查天线与 SMA 衰减器连接；射频调优每次仅变更单项参数并保留基线备份。
