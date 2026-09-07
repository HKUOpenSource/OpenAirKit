# systemd 模板与安装契约

这些 `.in` 文件表达设计，不是可安装产物。`@RELEASE@`、`@PYTHON@`、`@CONFIG@` 必须由后续安装器替换为本项目绝对路径，并验证相应 wrapper/模块存在。当前不提供安装器，也不 enable 任何服务。

| 模板 | 职责 |
| --- | --- |
| `aoc-stack.target.in` | 完整新栈生命周期，与旧 gNB 互斥 |
| `aoc-core.service.in` | 新 Compose 栈的 up/健康等待/stop |
| `aoc-gnb.service.in` | OCUDU 进程、B210 交接和 N2 就绪 |
| `aoc-collector.service.in` | 新栈数据采集 |
| `aoc-web.service.in` | 独立低权限 Web/API |

wrapper 待实现接口：

- `core up --wait`：只管理 `aoc-cn5g`，全部必需 NF 健康后返回；超时为非零，清理本次启动的资源。
- `core stop`：停止本项目容器，等待退出，保留数据卷及网络。
- `radio-preflight`：确认 RF 配置已验收、旧 gNB 已退出、B210 未被其他进程占用、绑定地址存在；异常拒绝启动，不杀死未知进程。
- `radio-health`：有限超时内确认本进程稳定且与指定新 AMF 建立 N2；不能把主机任意 SCTP 连接当成功。

gNB ExecStart 直接运行本项目二进制，使 systemd 跟踪真实主进程。默认 KillMode=control-group，停止需等待 UHD 句柄释放。`Restart=on-failure` 不应在 systemd 主动切换停止后重启争抢设备。

采集器模板中的权限限制是起点，具体 privileged helper / Docker 只读信息出口仍待设计；不把 Web 加入 docker 组。安装时建立独立用户、目录权限、RuntimeDirectory 和 StateDirectory 的共享组规则。所有模板最终必须经过目标机 `systemd-analyze verify` 和无射频替身服务测试。

只安装本项目 `aoc-*` units，不编辑 Biverge 的 unit 或脚本。默认均不配置开机自启，避免开机争抢 B210；后续由显式的启动策略选择一套 RAN。卸载时先停新栈，仅移除本项目文件并 daemon-reload。
