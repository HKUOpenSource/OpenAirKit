# Spark 安装指南

[English](setup-bs-spark.md)

本指南说明如何在 **DGX Spark** 上安装 **Spark Platform** 与 **OCUDU + Open5GS**
基站/核心网协议栈。硬件清单、端口表格与内核兼容性说明请参阅[硬件清单与拓扑](hardware-and-topology.zh-CN.md)
与[端口与运行时参考](reference/ports-and-runtime.zh-CN.md)。

## 前置条件

<table>
  <tr>
    <td align="center"><img src="assets/hardware/dgx-spark.webp" height="95" alt="DGX Spark" /><br/><sub><b>DGX Spark（ARM64 主机）</b></sub></td>
    <td align="center"><img src="assets/hardware/usrp-b210.webp" height="95" alt="USRP B210" /><br/><sub><b>Ettus USRP B210（USB 3.0）</b></sub></td>
  </tr>
</table>

- **主机**：DGX Spark（ARM64、Ubuntu 24.04、Python 3.12、`systemd`、Docker Engine 与 Compose）。
- **射频前端**：Ettus **USRP B210** 直连原生 USB 3.0 端口。
- **回环端口**：确认 `8877`（Spark Platform）与 `8879`（OCUDU JSON 指标）空闲；`8000–8002` 区间保持留空，供共驻 AI 推理服务使用。
- **锁定输入**：核对 `stacks/open5gs/artifacts.lock.json`、`stacks/open5gs/sources.lock.json`、`config/upstreams.json` 及 `config/network-contract.json`；订阅凭据保存于仓库外部的受保护存储中。

## 1. 安装 Spark Platform

通过 `make build-spark-release` 构建 ARM64 离线包并传输至 Spark，解压后依次执行
校验、主机检查与安装（首次安装会交互提示设置不少于 12 位的 Web 密码并加密写入
`/etc/aoc-monitor/auth.json`）：

```sh
python3 -I -B install.py verify --path .
python3 -I -B install.py check-host --path .
sudo python3 -I -B install.py install --path .
```

安装目标目录为 `/opt/agentic-ocudu/monitor`，`aoc-control.service`、
`aoc-observe.service` 与 `aoc-monitor-web.service` 默认不开启开机自启，且安装平台
不会干扰既有无线或核心网服务。

## 2. 安装 5G SA 协议栈

按照[Spark 协议栈部署](../deploy/spark/stack/README.zh-CN.md)编译 OCUDU 与准备
Open5GS 镜像、渲染并初始化私有鉴权 N6 核心网包，随后全新安装 `aoc-v2-core.service`、
`aoc-v2-radio.service`、`aoc-v2-cpu-latency.service` 与 `/usr/local/bin/aoc-v2ctl`。

建议同步启用遥测守护与共驻实时性隔离：

1. 运行 `sudo python3 scripts/spark/enable_radio_json_metrics.py`，开启仅限本机 root 访问的 `127.0.0.1:8879` 无线指标守护（`aoc-v2-metrics-guard.service`）。
2. 保持启用 `aoc-v2-cpu-latency.service`，在运行重型 AI 推理负载时按[端口与运行时参考](reference/ports-and-runtime.zh-CN.md)配置 `realtime.conf` 核芯亲和性。

## 3. 可选免密运维脚本与验收

- 若需免密 `~/aoc-ops/spark/` 快捷指令，请先按[维护助手指南](../deploy/maintenance/README.zh-CN.md)配置 `/usr/local/sbin/aoc-maintain`，再安装[Spark 运维](spark-operations.zh-CN.md)中的生命周期脚本。
- 通过 SSH 隧道访问 `127.0.0.1:8877`，核验 12 个核心网容器、gNB 进程代次、N2 NG Setup、`8879` 实时指标与网桥计数均正常；端到端数据通路最终通过 Jetson UE 侧绑定探测完成验收。
