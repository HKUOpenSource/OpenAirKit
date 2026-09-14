# V2 P3-01 Jetson 实机盘点

日期：2026-09-13
任务：V2-P3-01（完成）

## 只读结果

- Jetson 为 ARM64、Linux `5.15.148-tegra`、Python `3.10.12`；`ip`、`nmcli`、`iperf3`、`systemctl` 和 `fuser` 均可用。
- RM520N-GL `2c7c:0801` 暴露四个串口；USB interface `02` 唯一对应 `/dev/ttyUSB2`。同一 USB 父设备下唯一数据接口为 `enx62164330028c`，盘点时串口空闲。
- 唯一 Wi-Fi 接口在线，NetworkManager 正常。到 Spark 的管理路径经 `tailscale0`；到固定 ext-DN 的路径经 RM520N 数据接口。
- Jetson 内核对 `ip -j -4 rule show` 返回 `Operation not supported`。V2 使用 `constrained_static_routes`，保留 Wi-Fi/Tailscale 管理路径，并让连通性与测速显式绑定实际 RNDIS 接口。
- 旧 `oai-console` 已停止；早期 `aoc-jetson-agent/web` 为 failed，原因分别是历史 NM 连接删除回读错误和 SSE 停止超时。V2 不复用这些运行状态或数据库。

## 工具与回归

- 新增 `scripts/v2/jetson_inventory.py`，不发送 AT、不修改服务或网络，不输出 SIM、USB 序列号、SSID 或地址。
- 修复 `systemctl show --value` 顺序假设，改为按属性名解析。
- 三项模拟回归覆盖策略路由支持/不支持和重复 AT 口拒绝。

实机最终报告 `passed=true`。P3-01 通过。
