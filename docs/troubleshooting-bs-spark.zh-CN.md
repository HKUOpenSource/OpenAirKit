# Spark 故障排查

## 监测平台不可用或缺少无线指标

检查 `aoc-control.service`、`aoc-observe.service`、`aoc-monitor-web.service` 与
`127.0.0.1:8877`。端口冲突会在 `current` 链接变化前终止安装。健康接口正常但 SSE
中断时，先检查采集新鲜度和登录过期，再决定是否重启。

若主机与核心网指标正常但缺少 RAN 调度器指标：

- 通过 `ss -tna | grep :8879` 确认 `127.0.0.1:8879` 处于 `LISTEN`，且与 `aoc-observe`
  已建立 `ESTAB` 连接。
- 检查 `sudo nft -nn list table inet aoc_v2_metrics_guard`：规则应为
  `tcp dport 8879 meta skuid != 0 reject`（不应残留在 `8001` 上，以免影响共驻容器）。
- 若核心网网桥流量缺失，确认 `docker network inspect aoc-v2-open5gs-core` 返回有效网桥，
  以匹配 `collector.py::bridge_interface()` 动态解析结果。

## 无线栈启动失败

运行 `aoc-v2ctl status`，检查生命周期记录和无线 journal，并确认 B210 没有其他
持有者。区分 unit 失败与进程运行但 N2 未建立。稳定窗口失败后不要反复重启，应保留
日志和 invocation identifier。

- 若既有迁移主机在 `prepare` 阶段出现 `Unlisted release files` 或清单哈希不匹配，
  检查 `/opt/agentic-ocudu/v2/release.json`（早期 schema 2 迁移实例目录为 `units/`
  且清单中可能含历史备份文件，不应直接以 schema 3 `runtime.py` 整文件替换）。
- 检查 `systemctl show aoc-v2-radio.service -p DropInPaths`，确认不存在遗留的
  `/run/systemd/system/aoc-v2-radio.service.d/*.conf` 临时覆盖。

## 核心网功能异常

只检查对应容器及其依赖，记录退出码、OOM 和健康原因。N2、N3、N4、N6 是独立
证据域，一个接口健康不能抵消另一个接口故障。

若 `mongo`（8.0.30）在 Linux 7.0+ 内核（如 `7.0.0-1019-nvidia`）上因 TCMalloc
per-CPU rseq 崩溃，核查 `/opt/agentic-ocudu/v2/core/compose.json` 中是否包含
`GLIBC_TUNABLES=glibc.pthread.rseq=1`（仓库 `stacks/open5gs/compose/render.py` 已默认注入）。

## 设备显示过期或断开

对比当前 gNB 进程代次、RAN 上下文时间、核心网会话和 PDU 端点。gNB 重启前的会话
只能作为历史，直到出现新的关联证据。旧 IP 或旧测速不能将设备标记为当前在线。

## 射频错误或吞吐较低

在同一 gNB invocation 内比较 underflow、overflow 和 late。确认
`aoc-v2-cpu-latency.service` 处于 `active`（保持 `/dev/cpu_dma_latency=0`），
在有共驻推理任务的主机上核对 `realtime.conf`（CPU 亲和性与 `LimitRTPRIO=99`），并确认
B210 `rx_gain`（`54`）与 `cell_cfg.pusch.max_ue_mcs`（`24`）。记录 RSRP、RSRQ、
SINR、天线配置以及三次绑定 UE 接口的 benchmark。一次只修改一个无线、调度或
运行时变量，保留回滚，并在相同物理条件下复测。
