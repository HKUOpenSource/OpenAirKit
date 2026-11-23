# 协议栈服务定义

[English](README.md)

协议栈包安装 `aoc-v2-core.service` 和 `aoc-v2-radio.service`。
core 为保留 active 状态的 oneshot 服务；radio 依赖并绑定 core，以 `LimitRTPRIO=99`
直接运行 gNB 为主进程，启动后检查当前 N2 建链。两个 unit 均无 Install 段，不启用开机启动。
同目录下的站点审阅配套配置包括：`aoc-v2-cpu-latency.service`（`PartOf=aoc-v2-radio.service`，
配合 `aoc-v2-radio.service.d/cpu-latency.conf` 在无线运行时固定 `/dev/cpu_dma_latency=0`）
以及用于共驻负载主机的 `aoc-v2-radio.service.d/realtime.conf.example`。监测服务独立打包。
具体入口见[协议栈包指南](../README.zh-CN.md)。

安装时先用暂存可执行文件路径检查 unit 语法，再写入固定安装路径。本地测试以惰性
替身代替 systemd/Docker 命令，不能据此认定目标机 systemd 和射频行为已经验证。
