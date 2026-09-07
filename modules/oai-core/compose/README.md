# Compose 编排约定

本阶段只固定部署契约。完整 Compose 和 NF 配置将在镜像/订阅验证后生成，避免将缺少数据库初始化或健康依赖的示例误当成可部署核心网。

- Project：固定 `aoc-cn5g`；所有管理命令显式传入 `--project-name aoc-cn5g` 和绝对配置路径。
- Network：`aoc-cn5g-net`，专用 Linux bridge `aoc-cn5g`，CIDR `172.28.80.0/24`，gateway `.1`。
- NF：`mysql`、`nrf`、`amf`、`smf`、`upf`、`udr`、`udm`、`ausf`、`ext-dn`；采用 Compose 默认项目名前缀，不写旧栈 `container_name`。
- Volumes：由新项目创建数据库卷，不声明指向旧栈的 `external` 卷或 bind mount。
- 不使用 `network_mode: host`，不向宿主机发布 NF 的 80/8080/38412/2152/8805 等端口；gNB 通过 bridge 地址访问 NF。
- UPF 的 TUN、转发和 NAT 位于自己的网络命名空间；最小化设备与 capability 授权，不默认 `privileged: true`。
- ext-DN 返回路由只覆盖新 UE 地址池，下一跳新 UPF；如引入 iperf3，仅监听新 ext-DN 内部地址，避免占用宿主机 5201。
- 配置模板、数据库初始化与版本清单属于本模块，不从 Biverge 安装路径加载。
- 停止使用 `compose stop` 保留网络/数据；卸载只针对本项目资源。不能全局清理 Docker、路由、iptables 或执行 `down -v` 作为切换动作。

NF 启动顺序必须依据各镜像健康状态建立依赖；容器 running 不等于 AMF 接受 NGAP 或 UPF 可转发。核心网 wrapper 须有就绪超时、失败清理及准确退出码，接口见 `deploy/systemd/README.md`。
