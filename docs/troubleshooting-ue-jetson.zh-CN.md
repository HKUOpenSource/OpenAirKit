# Jetson 故障排查

[English](troubleshooting-ue-jetson.md)

当 **Jetson Orin** 终端侧出现异常时，可按以下现象逐项排查。

## Web 服务无法启动（`8878` 端口占用或权限异常）

- **`127.0.0.1:8878` 端口被占用**：执行 `ss -tlnp | grep 8878`，停用并禁用占端口的冲突单元后重新执行 `aoc-maintain start`。
- **服务权限报错（`203/EXEC`）**：核查已安装目录下的 `venv/` 对非特权服务账户可读可执行（`0755`/`0644`、无组/全局写权限），且 `/etc/aoc-v2-jetson/web.json` 权限为 `0640 root:aoc-v2-jetson-web`。

## 设备执行器异常或 USB 拓扑校验失败

- 执行 `/usr/local/sbin/aoc-maintain status`（或 `manage.py status`）并查看 `journalctl -u aoc-v2-jetson-device.service`。
- 对照[硬件与 TB01 附录](reference/hardware-notes.zh-CN.md#quectel-rm520n-gl-usb-接口布局)核实 `/etc/aoc-v2-jetson/device.json` 中的 `device.at_interface_number` 是否与当前 RNDIS/ECM 枚举匹配。修改时需先停止服务，并在启用开机自连时同步刷新 `/etc/aoc-v2-jetson/boot.json`。

## AT 串口被占用

- 切换至维护模式（或停止 `aoc-v2-jetson-device.service`），运行 `fuser /dev/ttyUSB*` 确认串口已释放，并检查 `ModemManager.service` 处于 disabled/masked 状态。切勿在进程仍持有串口时手动删除 `/var/lib/agentic-ocudu/v2-ue/serial.lock`。

## 注册或数据 PDU 失败

- 按 Overview 分层顺序逐级排查：SIM -> 服务小区 -> `C5GREG` 注册 -> 上下文定义 -> PDU 激活 -> 网卡 IPv4 地址。
- 若已注册且分配了 IPv4 地址但主机流量不通，按[硬件与 TB01 附录](reference/hardware-notes.zh-CN.md#rm520n-gl-qmap--mpdn-固件核查)核查 QMAP WWAN 与 MPDN 规则关联。

## 数据通路或诊断探测失败

- 核对模组接口 IPv4 地址、绑定主机路由及 `management_protected`（`Wi-Fi` + `tailscale0`）状态。手工测试必须显式绑定模组接口（如 `ping -I <modem-if> ...`），未绑定接口的 ping 在蜂窝未切主路由时会经 Wi-Fi 发出。
- `ext-DN` 的 TCP `8080 /health` 仅用于绑定探测健康检查，需与注册状态分开排查。

## 开机协调器中止或跳过执行

- 查看 `journalctl -u aoc-v2-jetson-boot.service` 与 `/var/lib/aoc-v2-jetson-boot/public/status.json`。
- **升级后校验和不匹配**：每次执行 `manage.py install` 升级后均须重新生成 `/etc/aoc-v2-jetson/boot.json`，以同步更新 `device_sha256` 与 `manifest_sha256`。
- **上联网关 ICMP 限速**：若管理 Wi-Fi 已连接但重试探测仍被网关丢弃，请检查上联网关的 ICMP 策略或 Wi-Fi 关联状态。
