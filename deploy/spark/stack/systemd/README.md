# systemd 模板与安装契约

这些 `.in` 文件不能直接安装。第一阶段由 `scripts/install_radio.py` 将 target/core/gnb 三个模板渲染为本项目固定版本的绝对路径，执行 `systemd-analyze verify` 后安装。监测平台模板仍待第二阶段实现；本安装器不安装监测服务，也不 enable 任何服务。

| 模板 | 职责 |
| --- | --- |
| `aoc-stack.target.in` | 完整协议栈生命周期，并与其他 gNB 进程互斥 |
| `aoc-core.service.in` | 接管已预热且健康的新 Compose 栈，停止时保留数据 |
| `aoc-gnb.service.in` | OCUDU 进程、B210 交接和 N2 就绪 |
| `aoc-collector.service.in` | 新栈数据采集 |
| `aoc-web.service.in` | 独立低权限 Web/API |

`scripts/radio_runtime.py` 已实现以下接口，生产安装和实机结果仍待验收：

- `core-check`：要求 CLI 已在射频交接前启动全部 10 服务并确认健康；没有健康核心网时返回非零。IMS 健康不等于 SIP 注册或通话验证。
- `core-stop`：停止本项目容器，等待退出，保留数据卷及网络。
- `preflight`：供 gNB 的 ExecStartPre 使用，确认配置已审查、冲突进程已退出、B210 未被占用及资源无冲突，异常拒绝启动。配置审查标志与实机验收标志分开。
- `handoff-check`：对应用户入口 `aocctl radio-preflight`，只读检查核心网、订阅标志和资源，不打开 B210。
- `health`：对应 `aocctl radio-health`，有限超时内确认本二进制的 PID、指定新 AMF 的 SCTP 连接和本轮 NG Setup 日志。

gNB ExecStart 直接运行本项目二进制，使 systemd 跟踪真实主进程。默认 KillMode=control-group，停止需等待 UHD 句柄释放。`Restart=no` 避免启动失败后反复争抢设备；target 通过 `BindsTo` 跟随 gNB 停止。第一阶段不拉起第二阶段的监控服务。

`scripts/test_systemd_switch.py` 已在 Spark 用户级 systemd 通过 5 次往返、5 组并发、启动失败和停止超时测试。它复用上述依赖关系并替换实际执行命令，不触碰 B210；不能替代生产安装和硬件验收。

采集器模板中的权限限制是起点，具体 privileged helper / Docker 只读信息出口仍待设计；不把 Web 加入 docker 组。安装时建立独立用户、目录权限、RuntimeDirectory 和 StateDirectory 的共享组规则。所有模板最终必须经过目标机 `systemd-analyze verify` 和无射频替身服务测试。

只安装本项目 `aoc-*` units，不编辑外部 unit 或脚本。默认均不配置开机自启，避免开机争抢 B210；RAN 必须通过显式操作启动。卸载时先停止本栈，仅移除本项目文件并执行 daemon-reload。
