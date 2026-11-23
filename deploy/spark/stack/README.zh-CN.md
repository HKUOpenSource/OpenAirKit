# Spark 协议栈部署

[English](README.md)

`runtime.py`、`package.py`、`libexec/` 与 `systemd/` 是独立 OCUDU/Open5GS 生命周期的现行源码，
与 Spark Platform 分开安装。源码 CLI 为 `python3 scripts/aocctl --help`，安装后为
`aoc-v2ctl`。旧模板与安装器已经归档，不参与打包。

## 准备私有候选包

使用 Python 3.10–3.12。在 ARM64 构建机执行
`python3 stacks/ocudu/scripts/build.py --workspace /path/to/private-radio --jobs 2`，
保留固定版本二进制及 `build-result.json`。使用已审阅的 UHD 安装编译探针，不运行它：

```sh
c++ -std=c++17 stacks/ocudu/scripts/probe_b210.cpp -o /path/to/private-radio/probe-b210 $(pkg-config --cflags --libs uhd)
```

Open5GS 镜像由 `stacks/open5gs/` 的固定构建输入提供。生成带鉴权和 N6 的私有核心网包：

```sh
python3 stacks/open5gs/compose/render.py --database-auth --n6 --output /path/to/private-core
```

当前支持仓库默认核心网子网、单数据 PDU 和十二项服务。MongoDB 卷初始化由
`stacks/open5gs/provision.py` 使用私有订阅材料和同一核心网包单独完成；该操作属于
后续明确安排的设备阶段，不能复制另一平台的数据库。下面的 staging 完全离线，
保留输入包及其私有凭据，不初始化数据库，也不启动服务。

```sh
python3 deploy/spark/stack/package.py stage \
  --core /path/to/private-core \
  --binary /path/to/private-radio/build/apps/gnb/gnb \
  --probe /path/to/private-radio/probe-b210 \
  --build-record /path/to/private-radio/build-result.json \
  --output /path/to/new-private-stack-release
python3 deploy/spark/stack/package.py verify --source /path/to/new-private-stack-release
```

staging 检查 ARM64 ELF 头、gNB 哈希和固定源码版本、核心网文件哈希与服务集合，
并记录探针、控制器和两个 unit 在内的全部文件。输出包含站点配置，是私有部署候选包，
不属于可公开分发的应用压缩包，不能加入 Git。

## 后续设备维护窗口安装

本次源码变更仅经过本地合成验证，目标机安装、服务校验和射频验收仍需后续执行。
私下传输已审阅候选包，校验独立记录的摘要；从可信 checkout 执行
`package.py verify --source CANDIDATE`，再在 ARM64 Linux 上执行
`sudo python3 deploy/spark/stack/package.py install --source CANDIDATE`。
安装器检查固定镜像、卷归属、资源冲突和 unit 语法，复制至 root 私有目录后再次校验，
安装 `/opt/agentic-ocudu/v2`、两个 V2 unit 和 `/usr/local/bin/aoc-v2ctl`。
安装不启用/启动服务，不更改订阅数据或监测平台。已有安装、unit 或 CLI 路径均拒绝覆盖；
这是全新安装入口，不是原位升级。失败时只清理本次新建文件。

安装后使用 `preflight`、`start`、`status`、`stop`。`prepare` 会打开空闲 B210，
核对身份/增益、写私有配置并执行 gNB dry-run；它要求核心网健康，通常作为 radio unit
的回调执行。`start` 通过 systemd 依赖先启动 core 再启动 radio，要求当前 SCTP 关联及
infoAPI 确认 NG Setup 成功。启动失败保留现场；停止先核对无线退出再停止 core，
不删除数据库卷。不要混用 CLI、Web、维护 helper 同时操作。

生成的 `compose.json` 默认为 `mongo` 服务注入 `GLIBC_TUNABLES=glibc.pthread.rseq=1`
以适配 Linux 7.0+ 内核与 MongoDB 8.0.30；`runtime.py` 默认生成 `tx_gain=80`、`rx_gain=54`
及 `cell_cfg.pusch.max_ue_mcs=24` 的私有 `gnb.json` 配置。

初始无线配置禁用遥测；另行安排 `scripts/spark/enable_radio_json_metrics.py` 事务
安装 `127.0.0.1:8879` 回环访问保护并启用 JSON 指标（已从 `8001` 迁移以避开共驻容器，且回滚时
会自动停止 `aoc-v2-metrics-guard.service`），再验收采集。`/dev/cpu_dma_latency` 低时延守护
（`libexec/aoc-v2-cpu-latency`、`systemd/aoc-v2-cpu-latency.service`、`cpu-latency.conf`）
及实时 CPU 绑定模板（`systemd/aoc-v2-radio.service.d/realtime.conf.example`）按站点审阅策略
配合 [协议栈服务定义](systemd/README.zh-CN.md) 使用。
