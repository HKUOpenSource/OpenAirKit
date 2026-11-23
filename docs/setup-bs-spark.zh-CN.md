# Spark 系统安装

## 前提

目标机应为 ARM64、Ubuntu 24.04、Python 3.12，并提供 systemd、Docker Compose 和通过 USB 3
连接的受支持 B210。确认 `127.0.0.1:8877`（Monitor Web）与 `127.0.0.1:8879`（OCUDU 回环
JSON 指标）空闲。端口 `8879` 用于避开共驻服务常占用的 `8000–8002` 区间（例如 DGX Spark 上的
本地 vLLM 容器）。监测平台、无线栈和核心网具有不同的发布与生命周期边界。

安装前核验 `stacks/open5gs/artifacts.lock.json` 的镜像摘要、
`stacks/open5gs/sources.lock.json` 的核心网源码版本、`config/upstreams.json` 的
OCUDU 版本，以及从 `config/network-contract.json` 派生的站点配置。生产订阅资料
只能从受保护的部署状态加载，不能进入仓库。

## 安装监测平台

使用 `make build-spark-release` 构建并传输 ARM64 发布包，再运行发布包内的
platform installer 完成 preflight 和 install。安装位置为
`/opt/agentic-ocudu/monitor`，三个平台服务（`aoc-control.service`、
`aoc-observe.service`、`aoc-monitor-web.service`）默认不开机自启。安装监测平台不会
启动或重启协议栈。

在解压后的 Spark 发布目录使用实际安装器动作：

```sh
python3 -I -B install.py verify --path .
python3 -I -B install.py check-host --path .
sudo python3 -I -B install.py install --path .
```

协议栈准备完成后，批准匹配的[维护包](../deploy/maintenance/README.zh-CN.md)
（`/usr/local/sbin/aoc-maintain`），并安装[Spark 生命周期脚本](spark-operations.zh-CN.md)。
完整启动和状态检查将 N2 建链与服务进程状态分开验证。

## 准备协议栈

按[独立协议栈包指南](../deploy/spark/stack/README.zh-CN.md)构建固定无线产物、生成并初始化
私有鉴权 N6 包，再用 `deploy/spark/stack/package.py` 暂存和校验。全新安装入口提供 V2
控制器、`aoc-v2-core.service`、`aoc-v2-radio.service` 与 `/usr/local/bin/aoc-v2ctl`，
不启动服务，也不覆盖已有安装。

当前维护基线包含已通过实机验证的配置保障：

- **MongoDB 内核兼容**：`stacks/open5gs/compose/render.py` 为 `mongo` 服务注入
  `GLIBC_TUNABLES=glibc.pthread.rseq=1`，用于兼容 Linux 7.0+ 内核（已在 `7.0.0-1019-nvidia`
  与 MongoDB `8.0.30` 验证）。
- **射频基线参数**：`deploy/spark/stack/runtime.py` 默认写入 `tx_gain=80`、`rx_gain=54`
  与 `cell_cfg.pusch.max_ue_mcs=24`。
- **低时延与实时调度资源**：`deploy/spark/stack/libexec/aoc-v2-cpu-latency`、
  `aoc-v2-cpu-latency.service`（`PartOf=aoc-v2-radio.service`）、`cpu-latency.conf`
  及 `realtime.conf.example`（`CPUAffinity`、`LimitRTPRIO=99`），用于避免 CPU 深度休眠及与
  共驻负载争抢核芯。
- **迁移实例（schema 2）与全新实例（schema 3）差异**：全新安装采用 schema 3 布局
  （`systemd/`，且新版 `runtime.py` 会拒绝目录内未登记文件）；若目标机属于带 schema 2 清单的
  既有迁移实例（使用 `units/` 并含历史备份目录），升级时应就地修补其现役 `runtime.py` 并更新
  `release.json` 哈希，不要直接用 schema 3 `runtime.py` 覆盖。

`scripts/spark/enable_radio_json_metrics.py` 提供带回滚事务的指标端口切换工具，可将未启用或旧版
`127.0.0.1:8001` 配置迁移到 `127.0.0.1:8879`，并安装 `aoc-v2-metrics-guard.service` 仅放行
`uid == 0`。接收 UE 流量前应核验 B210 所有权、核心网、N2 与 `8879` 回环指标端点。本地打包测试不代表
目标机安装或射频验收。

## 验证

通过 SSH 隧道访问 `127.0.0.1:8877`。验证全部 12 个核心网容器、gNB 进程代次、N2、`127.0.0.1:8879`
WebSocket 指标连接、动态解析后的核心网网桥计数器、当前 UE 上下文、活动 PDU 以及独立的 N3/N6 证据。
端到端数据路径必须由 Jetson 侧绑定接口的探测完成验收。
