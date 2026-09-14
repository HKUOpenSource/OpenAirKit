# Jetson Console 安装

## 前提

目标机应为 ARM64、Python 3.10，并提供 systemd、NetworkManager 和受支持的
RM520N 模组。任何路由修改前先确认 Wi-Fi 与 Tailscale 管理接口。端口
`127.0.0.1:8878` 必须空闲，模组串口不能被其他进程占用。

发布包必须包含 `RELEASE-VERSION`、已校验清单、锁定依赖、离线 wheelhouse 和
第三方许可材料。生产配置不得放入解压后的发布目录。

## 安装

在解压后的 Jetson 发布目录执行：

```sh
sudo ./deploy/install-jetson.sh preflight
sudo ./deploy/install-jetson.sh install
sudo /opt/agentic-ocudu/jetson/current/venv/bin/python -I \
  /opt/agentic-ocudu/jetson/current/deploy/manage.py status
```

安装位置是 `/opt/agentic-ocudu/jetson`。安装后
`aoc-v2-jetson-device.service` 与 `aoc-v2-jetson-web.service` 默认不开机
自启。启动前必须检查 preflight 报告中的管理接口。

## 验证

通过已安装的管理器启动平台，并用 SSH 隧道访问 `127.0.0.1:8878`。分别验证
登录、健康、SSE、模组发现、注册、数据 PDU 和绑定的数据路径。只有路由视图明确
使用模组接口后才运行短时测速。

维护和回滚见 [Jetson 运维](jetson-operations.zh-CN.md)，发现或数据验证失败见
[Jetson 故障排查](troubleshooting-ue-jetson.zh-CN.md)。
