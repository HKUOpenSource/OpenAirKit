<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/brand/logo-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/brand/logo-light.png">
  <img src="docs/assets/brand/logo-light.png" alt="OpenAirKit" width="540">
</picture>

<p><strong>面向 AI-RAN 的开源端到端 5G SA 实验与管控平台</strong></p>

<p>
  <img alt="5G SA: OCUDU + Open5GS" src="https://img.shields.io/badge/5G_SA-OCUDU_%2B_Open5GS-brightgreen">
  <img alt="Spark Platform: 0.2.1" src="https://img.shields.io/badge/Spark_Platform-0.2.1-blue">
  <img alt="Jetson Console: 0.6.2" src="https://img.shields.io/badge/Jetson_Console-0.6.2-blue">
  <img alt="Host: ARM64 Linux" src="https://img.shields.io/badge/Host-ARM64_Linux-green">
</p>

<p>
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="docs/quickstart.zh-CN.md">快速搭建</a> ·
  <a href="docs/architecture.zh-CN.md">系统架构</a> ·
  <a href="docs/hardware-and-topology.zh-CN.md">硬件清单</a> ·
  <a href="CONTRIBUTING.zh-CN.md">贡献指南</a> ·
  <a href="docs/README.zh-CN.md">文档总览</a>
</p>

</div>

**OpenAirKit** 基于 **OCUDU**（RAN）与 **Open5GS**（5GC），将 **DGX Spark +
USRP B210 + Jetson Orin + Waveshare M.2 5G 扩展载板 + Quectel RM520N-GL** 标准化
硬件平台构建为可稳定复现的 **5G 独立组网（SA）** IPv4 数据网络，并在基站与终端两侧
分别提供解耦的本地管控控制台。

<!-- ASSET_SLOT: docs/assets/hardware/kit-overview.jpg | 16:9 全套实验平台桌面部署实拍图 -->

## 核心能力

- **端到端标准化部署**：打通从物理连线、Open5GS 镜像构建、5G USIM 开户与烧录到 UE 用户面连通性验证的完整链路。
- **双端解耦的本地管控**：**Spark Platform** 与 **Jetson Console** 分别纳管基站与终端侧设备，具备 SSE 实时遥测、数据时效性判定、Wi-Fi/蜂窝路由自动切换与有界自愈能力。
- **端网侧可编程 AI 能力扩展**：基站与核心网侧采用 **DGX Spark**，终端侧采用 **Jetson Orin**，在链路两端分别提供**预留 AI 算力资源**、独立预留推理端口段及鉴权 REST/SSE 接口，便于开展**端网协同 AI 算法二次开发**与部署**自定义 AI 服务**。*（双端内置 AI 模块规划于后续阶段交付，详见[端网侧 AI 扩展指南](docs/ai-customization.zh-CN.md)。）*

## 系统架构

```mermaid
flowchart TB
  classDef hw fill:#f1f5f9,stroke:#475569,color:#0f172a
  classDef stack fill:#ecfdf5,stroke:#047857,color:#064e3b
  classDef mgmt fill:#eff6ff,stroke:#1d4ed8,color:#1e3a8a
  classDef ai fill:#fefce8,stroke:#a16207,stroke-dasharray:5 5,color:#713f12

  subgraph AI["可编程 AI 扩展层（自定义算法与推理流水线）"]
    direction LR
    JAI["Jetson 端侧 AI 运行环境"]:::ai
    SAI["DGX Spark 网侧 AI 运行环境"]:::ai
  end

  subgraph MGMT["本地优先管理平面"]
    direction LR
    JC["Jetson Console"]:::mgmt
    SP["Spark Platform"]:::mgmt
  end

  subgraph STACK["5G SA 协议栈平面"]
    direction LR
    RAN["OCUDU gNB"]:::stack
    CORE["Open5GS 5GC"]:::stack
    RAN -- "N2 / N3" --> CORE
  end

  subgraph HW["ARM64 硬件栈"]
    direction LR
    UEHW["Jetson Orin + RM520N-GL"]:::hw
    BSHW["DGX Spark +<br/>USRP B210"]:::hw
    UEHW <== "5G NR SA" ==> BSHW
  end

  UEHW --- JC
  BSHW --- RAN
  RAN -. "无线指标" .-> SP
  CORE -. "网元与会话状态" .-> SP
  JC -. "REST / SSE" .- JAI
  SP -. "REST / SSE" .- SAI
```

## 平台组成总览

<table>
  <tr>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/dgx-spark.webp" width="112" alt="DGX Spark" /><br/><sub><b>DGX Spark</b></sub></td>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/usrp-b210.webp" width="112" alt="USRP B210" /><br/><sub><b>USRP B210</b></sub></td>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/jetson-orin-nano.webp" width="112" alt="Jetson Orin Nano" /><br/><sub><b>Jetson Orin</b></sub></td>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/waveshare-m2-5g-carrier.webp" height="72" alt="Waveshare M.2 5G 扩展载板" /><br/><sub><b>M.2 5G 载板</b></sub></td>
    <td align="center" valign="bottom" width="20%"><img src="docs/assets/hardware/quectel-rm520n-gl.webp" height="72" alt="Quectel RM520N-GL" /><br/><sub><b>RM520N-GL</b></sub></td>
  </tr>
</table>

| 组件层级 | 软硬件角色 | 本地访问入口 | 技术参考 |
| --- | --- | --- | --- |
| **基站与核心网** | **DGX Spark** + **USRP B210** 运行 **OCUDU** 与 **Open5GS** | `aoc-v2ctl` / `systemctl` | [网络契约与射频基线](docs/reference/network-and-rf-profile.zh-CN.md) |
| **Spark Platform** | 基站侧采集器、Web 控制台与受限执行器（`apps/spark-platform/`） | `127.0.0.1:8877` | [Spark 运维](docs/spark-operations.zh-CN.md) |
| **UE 主机与模组** | **Jetson Orin** + **Waveshare M.2 5G 扩展载板** + **Quectel RM520N-GL** + 5G USIM | USB 3.0 + Wi-Fi 管理网 | [硬件清单与拓扑](docs/hardware-and-topology.zh-CN.md) |
| **Jetson Console** | UE 模组监管、路由自动切换与有界恢复（`apps/jetson-console/`） | `127.0.0.1:8878` | [Jetson 运维](docs/jetson-operations.zh-CN.md) |

两个控制台共用 `@aoc/console-ui`（`packages/console-ui/`），均仅维护本机状态，
且默认不随系统开机自启。

## 文档导航

| 分类 | 文档入口 |
| --- | --- |
| **快速了解** | [硬件清单与拓扑](docs/hardware-and-topology.zh-CN.md) · [端到端快速搭建指南](docs/quickstart.zh-CN.md) · [系统架构](docs/architecture.zh-CN.md) |
| **部署与开户** | [Spark 安装](docs/setup-bs-spark.zh-CN.md) · [协议栈部署](deploy/spark/stack/README.zh-CN.md) · [SIM 开户与烧录](docs/sim-provisioning.zh-CN.md) · [Jetson 安装](docs/setup-ue-jetson.zh-CN.md) |
| **运维与 AI 扩展** | [Spark 运维](docs/spark-operations.zh-CN.md) · [Jetson 运维](docs/jetson-operations.zh-CN.md) · [端网侧 AI 扩展指南](docs/ai-customization.zh-CN.md) |
| **故障排查** | [Spark 故障排查](docs/troubleshooting-bs-spark.zh-CN.md) · [Jetson 故障排查](docs/troubleshooting-ue-jetson.zh-CN.md) |
| **技术参考与附录（`L3`）** | [网络与射频基线](docs/reference/network-and-rf-profile.zh-CN.md) · [端口与运行时参考](docs/reference/ports-and-runtime.zh-CN.md) · [REST 与 SSE 接口](docs/reference/api-reference.zh-CN.md) · [硬件与 TB01 附录](docs/reference/hardware-notes.zh-CN.md) · [核心术语表](docs/reference/glossary.zh-CN.md) |

发布工程规范、产品路线图与视觉素材标准请参阅[完整文档目录](docs/README.zh-CN.md)。

## 仓库目录结构

- `apps/spark-platform/`：Spark 采集器、FastAPI 后端与 React Web 应用。
- `apps/jetson-console/`：Jetson 设备执行器、FastAPI 后端与 React Web 应用。
- `packages/console-ui/`：共享的 Astryx Core、Charts 与 Neutral 主题组件包。
- `stacks/ocudu/` 与 `stacks/open5gs/`：无线编译配置、Open5GS 容器构建、Compose 渲染与开户工具。
- `deploy/`：协议栈控制器、平台安装器、受限维护助手与可选 Jetson 开机协调器。
- `scripts/` 与 `config/`：离线 ARM64 发布脚本、指标防火墙守护、仓库审计与站点网络契约。
- `docs/`：中英文配对文档、技术参考附录（`docs/reference/`）与实机基线档案（`docs/acceptance/`）。

## 从源码构建与验证

需准备 Python `3.10–3.12` 与 Node.js `22`。

```sh
make install-dev BOOTSTRAP_PYTHON=python3.12
make check
```

若使用自定义虚拟环境路径，请在两条命令中同时传入 `VENV=local/dev-venv`。提交变更或构建
离线发布包前，请参阅[贡献指南](CONTRIBUTING.zh-CN.md)、[安全策略](SECURITY.md)与[发布指南](docs/releasing.zh-CN.md)。
