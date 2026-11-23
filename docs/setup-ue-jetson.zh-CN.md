# Jetson Console 安装

## 前提

使用 Linux ARM64、Python 3.10、systemd、NetworkManager 和受支持的 RM520N。
Wi-Fi 必须有唯一地址和唯一的 IPv4 回退网关；Tailscale 必须能路由到配置的
Spark 管理地址；模组必须取得自己的 RNDIS DHCP 地址。OCUDU 验证这些条件，
不会替换管理员拥有的默认路由，也不会停止外部服务。端口 `127.0.0.1:8878`
及发现的 AT 串口必须空闲。

取得 RNDIS DHCP 地址、且 `CGACT` 上下文已激活，并不代表主机数据已能转发。
对于已验证的 RM520N QMAP 固件，应检查默认 WWAN 及 MPDN 规则、连接状态是否
关联到所选数据 profile。当前 Console 配置数据上下文，但不创建 QMAP 规则，
也不开启自动拨号总开关。应分别读取 `AT+QMAPWAC?` 和每条规则的自动拨号标志。
缺少关联时应按厂商手册单独审核，保留既有 profile 与其他规则。下方验证记录
说明了已注册但数据不通的实测现象及受限站点修复流程。

commissioning 前，须将 `device.at_interface_number` 与实际 USB 布局对齐。
示例使用 `04`：RNDIS 占用 `00/01`，其后的 `02..05` 依次为 DIAG、GNSS、AT
和 modem 串口。如果四个串口位于 `00..03`、数据接口为 `04`，则 AT 接口使用
`02`。发现逻辑在打开串口前检查该拓扑，拒绝配置不匹配或未知的布局；不能仅凭
Linux 的 `ttyUSB` 编号确定 AT 功能。
实测布局与待验证项见 [RNDIS 发现验证记录](acceptance/2026-10-16-jetson-rndis-at.zh-CN.md)。

必要时先一次性配置站点 NetworkManager 连接。通过
`nmcli -f NAME,UUID,TYPE,DEVICE connection show --active` 检查活动连接，保持
管理 Wi-Fi 默认路由可用。既有默认路由的 metric 必须大于 10；metric 5、10 和
协议号 186 保留给应用自有默认路由。模组连接可启用或关闭 `ipv4.never-default`。应用连接配置
可能中断该链路，首次网络准备应在本地管理终端完成。这些是本站点的前置条件，
不借用其他项目的动作。

发布包包含已校验清单、ARM64 CPython 3.10 离线依赖、前端、安装器、生命周期
脚本及许可材料。生产配置放在发布目录外。从 0.6.0 开始，启停脚本包含在校验包内。

## 安装与初始化

在解压后的 Jetson 发布目录验证并安装：

```sh
python3 -I -B deploy/manage.py verify
python3 -I -B deploy/manage.py preflight
sudo bash deploy/install-jetson.sh
```

首次安装交互输入新的 Console 私有密码。程序安装到
`/opt/agentic-ocudu/jetson`，仅启动回环 Web 服务，两个 systemd 单元保持开机
启动 disabled。安装 shell 已选择 `install`，不要再追加 `install` 或 `preflight`。

commissioning 将安装绑定到本机 SIM 和管理接口。先停止 OCUDU，再将下面仅用于
文档示例的地址替换成 Spark 的实际管理地址：

```sh
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py commission \
  --spark-address 192.0.2.20 --wifi-interface auto
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py start
sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py status
```

`commission` 自动选择已安装应用的 Python 环境，不需要给系统 Python 安装模组
依赖。串口被占用时拒绝执行，已有 SIM 绑定与当前设备不一致时拒绝覆盖，不启动
服务、不写模组配置。该命令替代旧的 takeover 入口。初始化失败时保留安装供检查，
修正提示的条件后重试 commissioning，无需重新安装。

`start` 准备配置的数据探测路由和 Wi-Fi 回退默认路由，启动两个服务并恢复采集，
自动模组恢复保持暂停。连续两次新鲜的蜂窝验证（包含公网）成功后，将 IPv4 默认
出口切到蜂窝；连续两次失败后回退 Wi-Fi。证据过期、注册/PDU 或数据接口丢失时，
在下一次路由协调中立即回退。路由切换独立于自动模组恢复开关，不要求内核支持策略
路由。切换期间 Tailscale 可能重连；Wi-Fi 回退不等于独立且保证不断线的管理通道。
注册、PDU 和数据连通状态单独显示，启动不强制重连模组。

## 操作员权限与验收

管理员可直接使用已安装的管理器。需要免密快捷操作时，用仓库的
[受限维护批准包](../deploy/maintenance/README.md)构建并批准匹配的发布，再按
[Jetson 运维](jetson-operations.zh-CN.md)复制包内的三个脚本。维护助手用于既有
安装的升级，不代替首次安装及密码设置。维护批准与应用发布必须匹配。

通过 SSH 隧道打开 `127.0.0.1:8878`，分别检查服务、当前采集证据、SIM、注册、
PDU 及模组接口绑定的数据探测。正式使用前验证一次完整 OCUDU 停止/启动，包括
路由清理。除非管理员明确调整，两个服务均保持开机启动 disabled。

## 可选的开机协调

只启用两项平台服务并不足以完成开机验收：执行器退出时会主动暂停自动模组恢复，
systemd 初次启动执行器时，USB 枚举和 DHCP 也可能尚未就绪。可选的
[`boot_connect.py`](../deploy/jetson/boot_connect.py) 协调器支持经过审阅的现场
管理员安装，与固定发布并存；默认安装器不启用它。

执行器须先等待支持的 USB 拓扑、RNDIS DHCP、管理 Wi-Fi 和 Tailscale 就绪，
再执行原有启动检查。专用 NetworkManager 连接应按 RNDIS 驱动匹配，去掉失效的
网卡名或 MAC 绑定，启用自动连接并保持 `ipv4.never-default=yes`。蜂窝提升和
Wi-Fi 回退仍由平台根据有效探测负责。须避免 ModemManager 占用这台专用实验
模组，保留 NetworkManager 和 Wi-Fi 连接配置。

root 私有的 `/etc/aoc-v2-jetson/boot.json` 保存已批准的发布/设备配置哈希、SIM
身份承诺、USB 速率及受保护模组设置，不包含 SIM 鉴权密钥。开机协调器核对身份
和设置，先等待自然注册，必要时最多显式选择实验网一次，再执行一次标准 Device
Setup，要求自动恢复启用、蜂窝网口/源地址绑定的新鲜数据证据连续有效 120 秒。
它不重启整机，不改 USB 速率、SIM 文件、频段或 QMAP。命令完成状态不明时停止
后续发送；每次开机有持久化私有记录，脱敏状态可从
`/var/lib/aoc-v2-jetson-boot/public/status.json` 读取。

真实重启后须核对服务、boot ID、实际 USB 速率、实验网注册/会话、蜂窝普通出口
及独立 Wi-Fi 管理通路。两台 UE 应一次只配置和重启一台，通过验收后再处理另一台。
不能把服务 enable 成功等同于已验证开机恢复。
