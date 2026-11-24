# 端到端快速搭建指南

[English](quickstart.md)

本指南说明如何从硬件装配到业务验通，完成跨主机全链路 **5G SA** 数据通路部署，并通过
**Spark Console** 与 **Jetson Console** 实现双端纳管。

## 跨主机全链路部署流程

```mermaid
---
config:
  layout: elk
---
flowchart TB
  classDef ws fill:#f1f5f9,stroke:#475569,color:#0f172a
  classDef spark fill:#ecfdf5,stroke:#047857,color:#064e3b
  classDef jetson fill:#eff6ff,stroke:#1d4ed8,color:#1e3a8a

  subgraph WS1["1. 工作站"]
    direction LR
    S0["构建 ARM64<br/>离线发布包"]:::ws
  end

  subgraph SPARK["2. DGX Spark"]
    direction LR
    S1["部署 5G 协议栈与<br/>Spark Console"]:::spark
    S2A["Open5GS 添加<br/>独立订阅"]:::spark
    S1 --> S2A
  end

  subgraph WS2["3. 工作站"]
    direction LR
    S2B["烧录并校验<br/>5G USIM"]:::ws
  end

  subgraph JETSON["4. Jetson Orin"]
    direction LR
    S3["安装并初始化<br/>Jetson Console"]:::jetson
    S4["执行 Device Setup<br/>并端到端验收"]:::jetson
    S3 --> S4
  end

  S0 --> S1
  S0 -. "Jetson 发布包" .-> S3
  S2A --> S2B --> S3
```

## 前置准备

1. 按[硬件清单与拓扑](hardware-and-topology.zh-CN.md)完成物理连线与天线/衰减器装配。
2. 将 **DGX Spark** 与 **Jetson Orin** 接入同一 Tailscale 网络，确保 Jetson
   保留独立带外 Wi-Fi 管理默认网关的同时，经由 `tailscale0` 可达 Spark。
3. 在 macOS 或 Linux 工作站（Python `3.10–3.12`、Node.js `22`）生成离线 ARM64
   发布包，或使用经校验的发布归档：
   ```sh
   make install-dev BOOTSTRAP_PYTHON=python3.12
   make check
   make build-spark-release RELEASE_OUT=/tmp/aoc-spark-release
   make build-jetson-release RELEASE_OUT=/tmp/aoc-jetson-release
   ```
4. 在 Git 仓库之外创建受限本地目录（`chmod 0700`），集中存放 SIM 鉴权密钥与站点核心网包。

---

## 第 1 步 — 部署 Spark 5G 协议栈与 Spark Console

在 **DGX Spark** 上执行：

1. **构建 OCUDU 与 Open5GS 运行时镜像**：
   - 按[Spark 协议栈部署](../deploy/spark/stack/README.zh-CN.md)编译锁定版本的 `gnb` 与 `probe-b210`。
   - 按 [Open5GS ARM64 构建](../stacks/open5gs/build/README.md)制作基础镜像，随后构建两款运行时衍生镜像：
     ```sh
     docker build -f stacks/open5gs/build/Dockerfile.n6 -t aoc-open5gs-n6:local .
     docker build -f stacks/open5gs/build/Dockerfile.connectivity -t aoc-open5gs-connectivity:local .
     ```
     核对镜像标签与摘要同 `stacks/open5gs/artifacts.lock.json` 一致后，按[Spark 协议栈部署](../deploy/spark/stack/README.zh-CN.md)渲染编排（`--database-auth --n6`）、初始化 MongoDB 并安装 `aoc-v2ctl`。
2. **安装 Spark Console**：
   上传并解压 Spark 离线包，依次完成包校验、主机预检与安装（首次安装将交互提示设置不少于 12 位的 Web 密码）：
   ```sh
   python3 -I -B install.py verify --path .
   python3 -I -B install.py check-host --path .
   sudo python3 -I -B install.py install --path .
   ```
3. **开启 OCUDU 指标并启动全部服务**：
   ```sh
   sudo python3 scripts/spark/enable_radio_json_metrics.py
   sudo aoc-v2ctl start
   sudo systemctl start aoc-control.service aoc-observe.service aoc-monitor-web.service
   ```
4. **验证基站与平台就绪**：
   确认 `sudo aoc-v2ctl status` 显示 12 个核心网容器均健康且 N2 NG Setup 成功，
   且 `curl -fsS http://127.0.0.1:8877/api/v1/health` 返回 `ok`。

---

## 第 2 步 — Open5GS 开户与 5G USIM 烧录

按照[Open5GS 开户与 5G USIM 烧录指南](sim-provisioning.zh-CN.md)完成以下操作：

1. 在 **DGX Spark** 上运行 `stacks/open5gs/subscriber.py`，依据[网络契约与射频基线](reference/network-and-rf-profile.zh-CN.md)创建独立订阅。
2. 在工作站上为支持 5G Milenage 的可编程 USIM 卡写入匹配的 `IMSI`、`Ki` 与 `OPc`，完成回读核对与本地 Milenage 向量测试。

---

## 第 3 步 — 部署 Jetson Console 并接入 UE

在 **Jetson Orin** 上执行：

1. **核验硬件装配与管理网络**：
   确认 **Quectel RM520N-GL** 与 Nano-SIM 已装入 Waveshare 载板、`ModemManager` 已停用并屏蔽、Wi-Fi 带外管理网关可用且 `tailscale0` 可达 Spark。
2. **安装、初始化并启动 Jetson Console**：
   解压 Jetson 离线包（首次安装会交互提示设置控制台密码），将下列 `192.0.2.20` 替换为 Spark 的实际 Tailscale IP：
   ```sh
   python3 -I -B deploy/manage.py verify
   python3 -I -B deploy/manage.py preflight
   sudo bash deploy/install-jetson.sh
   sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
   sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py commission \
     --spark-address 192.0.2.20 --wifi-interface auto
   sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py start
   ```
3. **验证服务健康并运行 Device Setup**：
   确认 `curl -fsS http://127.0.0.1:8878/api/v1/health` 返回 `ok`，建立 SSH 隧道
   （`ssh -L 8878:127.0.0.1:8878 <user>@<jetson-host>`）登录 `http://127.0.0.1:8878`，
   并在 **Device Setup** 页面触发入网流程。

---

## 第 4 步 — 端到端联调验收与可选进阶配置

1. **核对双端运行状态**：
   - **Jetson Overview（`127.0.0.1:8878`）**：确认 SIM 就绪、NR SA 注册成功、已分配活动 IPv4 PDU、绑定数据探测通过、蜂窝优先路由生效且 `management_protected = true`。
   - **Spark Console（`ssh -L 8877:127.0.0.1:8877 <user>@<spark-host>`）**：确认实时无线遥测、关联 UE RNTI 上下文、活动 PDU 会话及 N3/N6 网桥计数持续更新。
2. **可选进阶配置**：
   - 启用受限免密运维脚本（`~/aoc-ops/*/start.sh`）：参阅[维护助手指南](../deploy/maintenance/README.zh-CN.md)。
   - 启用无人值守冷重启自连（`boot_connect.py`）：参阅[Jetson Console 安装指南](setup-ue-jetson.zh-CN.md#3-可选的开机协调)。
   - 基于端网预留算力开展 AI 算法二次开发与扩展集成：参阅[端网侧 AI 扩展指南](ai-customization.zh-CN.md)。
