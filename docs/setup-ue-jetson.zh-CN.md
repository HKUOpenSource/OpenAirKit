# Jetson Console 安装

[English](setup-ue-jetson.md)

> [!TIP]
> 关于 UE 侧硬件清单（含使用 **[Waveshare SIM8262E-M2 5G for Jetson Orin](https://www.waveshare.net/shop/SIM8262E-M2-5G-for-Jetson-Orin.htm)**
> 载板安装 **Quectel RM520N-GL** 模组）与 0→1 联调顺序，请先阅读
> [硬件清单与拓扑](hardware-and-topology.zh-CN.md)与[端到端快速搭建指南](quickstart.zh-CN.md)。

## 前提

使用 Linux ARM64、Ubuntu 22.04、Python 3.10、systemd、NetworkManager 和受支持的
**Quectel RM520N-GL**（安装在上述 Waveshare Jetson Orin M.2 5G 扩展载板上，经 USB 3.0
接入 Jetson）。Wi-Fi 必须有唯一地址和唯一的 IPv4 回退网关；Tailscale 必须能路由到
配置的 Spark 管理地址；模组必须取得自己的 RNDIS 或 ECM（`cdc_ether`）DHCP 地址。
OCUDU 验证这些条件，不会替换管理员拥有的默认路由，也不会停止外部服务。端口
`127.0.0.1:8878` 及发现的 AT 串口必须空闲（如有冲突的旧控制台服务或 ModemManager
占用了 `8878` 端口或 AT 串口，应预先停用并禁用）。

取得模组 DHCP 地址且 `CGACT` 上下文已激活，并不代表主机数据已能转发。对于已验证的
RM520N QMAP 固件，应检查默认 WWAN 及 MPDN 规则、连接状态是否关联到所选数据 profile。
当前 Console 配置数据上下文，但不创建 QMAP 规则，也不开启自动拨号总开关。应分别读取
`AT+QMAPWAC?` 和每条规则的自动拨号标志。缺少关联时应按厂商手册单独审核，保留既有
profile 与其他规则。实测现象及受限站点修复流程见
[RNDIS 发现验证记录](acceptance/2026-10-16-jetson-rndis-at.zh-CN.md)。

在 commissioning 或升级前，须将 `/etc/aoc-v2-jetson/device.json` 中的
`device.at_interface_number` 与实际 USB 布局对齐。`aoc_jetson.hardware.discover()`
会在打开任何串口前校验以下三种 RM520N 拓扑（不能仅凭 Linux `ttyUSB` 编号判断 AT 功能）：

| USB 数据驱动 | 数据接口 `bInterfaceNumber` | 串口 `bInterfaceNumber`（`DIAG/GNSS/AT/Modem`） | 所需 `at_interface_number` |
| --- | --- | --- | --- |
| `rndis_host`（RNDIS） | `00/01` | `02`、`03`、`04`、`05` | `"04"` |
| `cdc_ether`（ECM） | `04` | `00`、`01`、`02`、`03` | `"02"` |
| `cdc_ether`（ECM） | `0a` | `00`、`01`、`02`、`03` | `"02"` |

必要时先一次性配置站点 NetworkManager 连接。通过
`nmcli -f NAME,UUID,TYPE,DEVICE connection show --active` 检查活动连接，保持管理 Wi-Fi
默认路由可用。既有默认路由的 metric 必须大于 10；metric 5、10 和协议号 186 保留给
应用自有默认路由。模组连接可启用或关闭 `ipv4.never-default`。应用连接配置可能中断
该链路，首次网络准备应在本地管理终端完成。

0.6.2 发布包包含已校验清单、ARM64 CPython 3.10 离线依赖、前端、安装器
（`deploy/manage.py`）、生命周期脚本及许可材料。生产配置放在发布目录外。从 0.6.2 起，
`manage.py` 在创建 `venv/` 时会临时切换到 `os.umask(0o022)`，并在 `private_write()`
中显式执行 `os.chmod(..., mode)`，确保即使在 `umask 077` 环境下，`venv/` 与
`web.json`（`0640 root:aoc-v2-jetson-web`）仍对非特权 Web 服务可读。

## 安装与初始化

在解压后的 Jetson 发布目录验证并安装：

```sh
python3 -I -B deploy/manage.py verify
python3 -I -B deploy/manage.py preflight
sudo bash deploy/install-jetson.sh
```

首次安装交互输入新的 Console 私有密码。程序安装到 `/opt/agentic-ocudu/jetson`，仅启动
回环 Web 服务，两个 systemd 单元保持开机启动 disabled。安装 shell 已选择 `install`，
不要再追加 `install` 或 `preflight`。

commissioning 将安装绑定到本机 SIM 和管理接口。先停止 OCUDU，再将下面仅用于文档示例的
地址替换成 Spark 的实际管理地址：

```sh
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py commission \
  --spark-address 192.0.2.20 --wifi-interface auto
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py start
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py status
```

`commission` 自动选择已安装应用的 Python 环境，不需要给系统 Python 安装模组依赖。
串口被占用时拒绝执行，已有 SIM 绑定与当前设备不一致时拒绝覆盖，不启动服务、不写模组
配置。初始化失败时保留安装供检查，修正提示的条件后重试 commissioning，无需重新安装。

`start` 准备配置的数据探测路由和 Wi-Fi 回退默认路由，启动两个服务并恢复采集，
自动模组恢复保持暂停。连续两次新鲜的蜂窝验证（包含公网）成功后，将 IPv4 默认出口
切到蜂窝；连续两次失败后回退 Wi-Fi。证据过期、注册/PDU 或数据接口丢失时，在下一次
路由协调中立即回退。路由切换独立于自动模组恢复开关。

## 操作员权限与验收

管理员可直接使用已安装的管理器。需要免密快捷操作时，用仓库的
[受限维护批准包](../deploy/maintenance/README.zh-CN.md)构建并批准匹配的发布，再按
[Jetson 运维](jetson-operations.zh-CN.md)安装三个生命周期脚本。维护助手用于既有安装的
升级，不代替首次安装及密码设置。维护批准与应用发布必须匹配。

通过 SSH 隧道打开 `127.0.0.1:8878`，分别检查服务、当前采集证据、SIM、注册、
PDU 及模组接口绑定的数据探测。正式使用前验证一次完整 OCUDU 停止/启动，包括路由清理。
除非管理员明确按下方步骤配置，两个服务保持开机启动 disabled。

## 可选的开机协调

只启用两项平台服务并不足以完成开机验收：执行器退出时会主动暂停自动模组恢复，systemd
初次启动执行器时，USB 枚举和 DHCP 也可能尚未就绪。可选的
[`boot_connect.py`](../deploy/jetson/boot_connect.py) 协调器独立安装在
`/opt/agentic-ocudu/jetson/boot_connect.py`（位于不可变应用发布包之外），支持经过
审阅的现场安装，默认安装器不启用它。

在已完成 commissioning 的主机上启用开机协调时遵循以下步骤：

1. **避免 ModemManager 接管模组**，保持 NetworkManager 管理 Wi-Fi 与模组 DHCP（模组
   profile 建议开启 `ipv4.never-default=yes`，外部默认路由 metric 大于 10）。
2. **在 `aoc-v2-jetson-device.service` 停止状态（AT 串口空闲时）先做只读 AT 兼容预检**：
   确认目标 RNDIS 或 ECM 固件上 `boot_connect.Serial`、`configuration()`（读取
   `AT+CGDCONT?`、`AT+QMAPWAC?`、`AT+QMAP="MPDN_rule"`、`AT+QCFG="usbnet"`、
   `AT+QCFG="usbspeed"`、`AT+QNWPREFCFG="nr5g_band"`、`AT+QNWPREFCFG="nr5g_disable_mode"`、
   `AT+QNWPREFCFG="mode_pref"`）与 `usb_speed()` 全部成功返回。
3. **在完成 `aoc-maintain install` / `manage.py install` 之后生成 root 私有的 `/etc/aoc-v2-jetson/boot.json`（`0600`）**：
   因为安装动作会更新 `device.json["release"]` 和 `revision`，必须在安装完成后再计算
   `device_sha256` 与 `manifest_sha256`，连同 `sim_sha256`、`usb_speed_mbps` 和
   `modem_configuration` 写入 `boot.json`（不含 SIM 鉴权密钥）；并创建状态目录
   `/var/lib/aoc-v2-jetson-boot/private`（`0700`）和 `public`（`0755`）。
4. **安装 systemd drop-in 与开机服务**：
   - `/etc/systemd/system/aoc-v2-jetson-device.service.d/boot-ready.conf` 设置
     `TimeoutStartSec=360`，先以 `ExecStartPre=` 清空原有列表，再按顺序执行
     `boot_connect.py ready` → `site_guard.py` →
     `network_entry.py --config /etc/aoc-v2-jetson/device.json --action fallback`，确保
     `device_entry.py` 启动前 USB 拓扑、模组 DHCP、管理 Wi-Fi 与 Tailscale 均已就绪。
   - `/etc/systemd/system/aoc-v2-jetson-boot.service`（`Type=oneshot`、`RemainAfterExit=yes`、
     `After=aoc-v2-jetson-device.service aoc-v2-jetson-web.service`）最多等待 30 秒直至
     `/run/aoc-v2-jetson/device.sock` 就绪，再运行 `/usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/boot_connect.py connect`
     （`TimeoutStartSec=1200`），等待自然注册（必要时最多显式选网一次）、发起一次标准 Setup，
     并要求带自动恢复启用的蜂窝绑定数据连续稳定 120 秒。

每次开机会以主机 `boot_id` 为键写入持久化私有日志（禁止同次开机重放），并将脱敏状态输出到
`/var/lib/aoc-v2-jetson-boot/public/status.json`。真实冷重启后须核对服务、boot ID、实际
USB 速率、实验网注册/会话、蜂窝普通出口及独立 Wi-Fi 管理通路。两台 UE 应逐台配置重启验收，
不能把 `systemctl enable` 成功等同于已完成冷重启开机自连验收。
