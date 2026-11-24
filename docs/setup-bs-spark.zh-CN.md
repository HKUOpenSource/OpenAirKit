# Spark 安装指南

[English](setup-bs-spark.md)

本指南说明如何在 **DGX Spark** 上安装 **Spark Console** 与 **OCUDU + Open5GS**
基站及核心网协议栈。硬件清单、端口规划与内核兼容性说明请参阅[硬件清单与拓扑](hardware-and-topology.zh-CN.md)
及[端口与运行时参考](reference/ports-and-runtime.zh-CN.md)。

## 前置条件

<table>
  <tr>
    <td align="center" valign="middle" width="50%"><img src="assets/hardware/dgx-spark.webp" width="145" alt="DGX Spark" /></td>
    <td align="center" valign="middle" width="50%"><img src="assets/hardware/usrp-b210.webp" width="145" alt="USRP B210" /></td>
  </tr>
  <tr>
    <td align="center" valign="top"><sub><b>DGX Spark（ARM64 主机）</b></sub></td>
    <td align="center" valign="top"><sub><b>Ettus USRP B210（USB 3.0）</b></sub></td>
  </tr>
</table>

- **主机环境**：DGX Spark（ARM64、Ubuntu 24.04、Python 3.12、`systemd`、Docker Engine 与 Compose 插件）。
- **射频前端**：Ettus **USRP B210** 直连原生 USB 3.0 端口。
- **回环端口**：确认 `8877`（Spark Console）与 `8879`（OCUDU JSON 指标）空闲；`8000–8002` 作为独立预留推理端口段保持留空。
- **锁定输入**：核验 `stacks/open5gs/artifacts.lock.json`、`stacks/open5gs/sources.lock.json`、`config/upstreams.json` 及 `config/network-contract.json`；订阅凭据须保存在 Git 之外的受保护目录中。

## 1. 安装 Spark Console

通过 `make build-spark-release` 构建 ARM64 离线包并传输解压至 Spark，依次运行完整性
校验、主机预检与安装（首次安装将交互提示设置不少于 12 位的 Web 密码并经哈希后写入
`/etc/aoc-monitor/auth.json`）：

```sh
python3 -I -B install.py verify --path .
python3 -I -B install.py check-host --path .
sudo python3 -I -B install.py install --path .
```

安装程序将运行时部署至 `/opt/agentic-ocudu/monitor`，`aoc-control.service`、
`aoc-observe.service` 与 `aoc-monitor-web.service` 默认不随开机自启；安装过程不干扰
既有无线与核心网服务。

## 2. 安装 5G SA 协议栈

依据[Spark 协议栈部署](../deploy/spark/stack/README.zh-CN.md)编译 OCUDU、构建 Open5GS
运行镜像并渲染初始化私有鉴权 N6 核心网部署包，随后安装 `aoc-v2-core.service`、
`aoc-v2-radio.service`、`aoc-v2-cpu-latency.service` 与 `/usr/local/bin/aoc-v2ctl`。

建议同步启用指标守护与无线实时性隔离：

1. 运行 `sudo python3 scripts/spark/enable_radio_json_metrics.py`，开启仅限本机 root 访问的 `127.0.0.1:8879` 无线指标守护（`aoc-v2-metrics-guard.service`）。
2. 保持启用 `aoc-v2-cpu-latency.service`，在运行高负载 AI 推理任务时参照[端口与运行时参考](reference/ports-and-runtime.zh-CN.md)配置 `realtime.conf` CPU 核芯亲和性。

## 3. 可选受限运维脚本与系统验收

- 若需启用免密 `~/aoc-ops/spark/` 运维脚本，请先按[维护助手指南](../deploy/maintenance/README.zh-CN.md)配置 `/usr/local/sbin/aoc-maintain`，再部署[Spark 运维](spark-operations.zh-CN.md)所述的生命周期脚本。
- 通过 SSH 端口转发访问 `127.0.0.1:8877`，核验 12 个核心网容器、gNB 进程实例代次、N2 NG Setup、`8879` 实时指标与网桥计数均正常；最终结合 Jetson UE 侧绑定探测完成端到端数据面验收。
