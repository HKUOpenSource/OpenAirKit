# Jetson Console 安装指南

[English](setup-ue-jetson.md)

本指南说明如何在 **Jetson Orin** 上安装、初始化 **Jetson Console**，并可选开启针对
**[Waveshare SIM8262E-M2 5G for Jetson Orin](https://www.waveshare.net/shop/SIM8262E-M2-5G-for-Jetson-Orin.htm)**
载板与 **Quectel RM520N-GL** 模组的无人值守冷重启自连。

## 前置条件

- **主机与系统**：Jetson Orin（ARM64、Ubuntu 22.04、Python 3.10、`systemd`、`NetworkManager`）。
- **模组与 USB**：Quectel RM520N-GL 装入 Waveshare 载板并接入 USB 3.0；停用并屏蔽 `ModemManager.service`；确保 `127.0.0.1:8878` 空闲。按[硬件与 TB01 附录](reference/hardware-notes.zh-CN.md)核对 `/etc/aoc-v2-jetson/device.json` 中的 `device.at_interface_number` 与当前 RNDIS/ECM 布局一致。
- **管理网络**：Wi-Fi 具备独立 IPv4 回退网关，且 `tailscale0` 可路由到达 Spark 管理地址。外部或管理员默认路由 metric 须严格大于 `10`，使 Jetson Console 的协议 `186` 路由策略（Wi-Fi `metric 5` / 蜂窝 `metric 10`）正常运行而不改变外部配置。

## 1. 安装与初始化（Commissioning）

通过 `make build-jetson-release` 构建 ARM64 离线包并传输解压至 Jetson Orin，依次执行
校验、预检与安装（首次安装会交互提示设置新的控制台密码）：

```sh
python3 -I -B deploy/manage.py verify
python3 -I -B deploy/manage.py preflight
sudo bash deploy/install-jetson.sh
```

程序安装于 `/opt/agentic-ocudu/jetson`，仅启动回环 Web 服务，两个 systemd 单元默认保持
开机不自启。

随后停止 Jetson Console，使用 Spark 的实际管理 IPv4 地址（替换下方示例占位符
`192.0.2.20`）运行 `commission` 并启动服务：

```sh
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py commission \
  --spark-address 192.0.2.20 --wifi-interface auto
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py start
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py status
```

`commission` 会自动选用已安装的应用运行环境，并将当前实例绑定到在插 SIM 指纹与管理网口。

## 2. 通过 Web 控制台验证

1. 通过 SSH 隧道打开 `127.0.0.1:8878` 并登录 **Overview** / **Device Setup**。
2. 触发 **Device Setup**，确认 SIM 就绪、NR SA 注册成功、获得活动 IPv4 PDU、绑定数据探测通过、`management_protected = true`，且连续探测通过后自动切换至蜂窝默认路由。
3. 正式使用前验证一次完整的 `manage.py stop` 与 `manage.py start` 周期（包括路由清理）。

如需配置免密快捷指令（`~/aoc-ops/jetson/start.sh`），请按[维护助手指南](../deploy/maintenance/README.zh-CN.md)部署对应批准包并参阅[Jetson 运维](jetson-operations.zh-CN.md)。

## 3. 可选的开机协调

如需开启无人值守冷重启自连（将 `deploy/jetson/boot_connect.py` 部署至 `/opt/agentic-ocudu/jetson/boot_connect.py`）：

1. **在 `aoc-v2-jetson-device.service` 停止时完成只读 AT 预检**：核对[硬件与 TB01 附录](reference/hardware-notes.zh-CN.md#rm520n-gl-qmap--mpdn-固件核查)列出的 AT 查询与 USB 速率检查均正常返回。
2. **在安装应用后生成 `/etc/aoc-v2-jetson/boot.json`（`0600`，root 持有）**：确保其中 `device_sha256`、`manifest_sha256`、`sim_sha256`、`usb_speed_mbps` 与 `modem_configuration` 与现役安装一致（不含任何 SIM 密钥），并创建 `/var/lib/aoc-v2-jetson-boot/private`（`0700`）与 `public`（`0755`）。
3. **部署 systemd drop-in 与开机一次性服务**：
   - `/etc/systemd/system/aoc-v2-jetson-device.service.d/boot-ready.conf`：设置 `TimeoutStartSec=360`，以 `ExecStartPre=` 重置后依次执行 `boot_connect.py ready` -> `site_guard.py` -> `network_entry.py --config /etc/aoc-v2-jetson/device.json --action fallback`，确保 USB 枚举、模组 DHCP、Wi-Fi 与 `tailscale0` 就绪后再启动 `device_entry.py`。
   - `/etc/systemd/system/aoc-v2-jetson-boot.service`（`Type=oneshot`、`After=aoc-v2-jetson-device.service aoc-v2-jetson-web.service`）：最长等待 `30 s` 直至 `/run/aoc-v2-jetson/device.sock` 就绪，随后运行 `/usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/boot_connect.py connect`（`TimeoutStartSec=1200`）执行标准入网流程并验证带自动恢复的稳定数据通道。
4. **真实冷重启验收**：重启后核查 systemd 状态、`boot_id`、`/var/lib/aoc-v2-jetson-boot/public/status.json`、蜂窝普通出口以及独立 Wi-Fi/`tailscale0` 管理可访问性。多台 UE 场景请逐台配置与重启验收。
