# 端到端快速搭建指南

[English](quickstart.md)

本指南提供从零硬件到端到端 5G SA 通路联调的完整主线路径，并说明如何接入 **Spark Platform** 与 **Jetson Console**。每个步骤都附带明确的验收判定条件；详细参数与边界请点击对应专题文档查看。

```mermaid
flowchart LR
  S0["0. 硬件与前置检查"] --> S1["1. 拉起 Spark 5G 栈与平台"]
  S1 --> S2["2. Open5GS 开户与 TB01 写卡"]
  S2 --> S3["3. 部署 Jetson Console 与 UE 入网"]
  S3 --> S4["4. 端到端联调与可选冷启动自连"]
```

## 准备阶段

1. 按[硬件清单、拓扑结构与前置条件](hardware-and-topology.zh-CN.md)完成物理接线与操作系统前置检查。
2. 如从源码构建发布包，先在开发机验证工具链与仓库审计：
   ```sh
   make install-dev BOOTSTRAP_PYTHON=python3.12
   make check
   ```
3. 在仓库外部建立受限目录（`chmod 0700`）保存站点的 SIM 密钥、发布候选包和备份；严禁将凭据或生产配置提交进 Git。

---

## 第 1 步 — 部署 Spark 5G 协议栈与 Spark Platform

在 **DGX Spark**（或 ARM64 构建机）上执行：

1. **构建并安装 OCUDU + Open5GS 协议栈**：
   按照[独立协议栈包指南](../deploy/spark/stack/README.zh-CN.md)构建固定版本的 OCUDU `gnb` 与 `probe-b210`，生成带鉴权和 N6 的私有核心网配置（`stacks/open5gs/compose/render.py --database-auth --n6`），初始化 MongoDB（`stacks/open5gs/provision.py`），再使用 `deploy/spark/stack/package.py` 完成暂存、校验和安装。
2. **构建并安装 Spark Platform（`0.2.1`）**：
   通过 `make build-spark-release` 构建离线发布包（参见[发布指南](releasing.zh-CN.md)），传送至 Spark 后按[Spark 系统安装](setup-bs-spark.zh-CN.md)依次执行 `install.py verify`、`check-host` 与 `sudo python3 -I -B install.py install --path .`。
3. **开启受守护的 OCUDU JSON 指标（`127.0.0.1:8879`）**：
   运行 `scripts/spark/enable_radio_json_metrics.py`，将无线遥测端口固定在 `127.0.0.1:8879` 并启用 `aoc-v2-metrics-guard.service`（避开 `8000–8002`）。
4. **（可选）部署受限维护助手与运维快捷脚本**：
   按[维护助手指南](../deploy/maintenance/README.zh-CN.md)安装 `/usr/local/sbin/aoc-maintain`，并将 `start.sh`、`stop.sh`、`platformctl.py` 放到 `~/aoc-ops/spark/`。
5. **启动基站、核心网与监测平台**：
   ```sh
   ~/aoc-ops/spark/start.sh
   /usr/bin/python3 -I ~/aoc-ops/spark/platformctl.py status
   curl -fsS http://127.0.0.1:8877/api/v1/health
   ```

**第 1 步通过标准**：
- `aoc-v2-open5gs` 全部 12 个核心网容器处于健康状态；
- `aoc-v2-radio.service` 与 `aoc-v2-cpu-latency.service` 处于 `active`，Open5GS infoAPI 确认 N2 NG Setup 成功；
- `http://127.0.0.1:8877/api/v1/health` 返回 `ok`。

---

## 第 2 步 — 在 Open5GS 开户并烧录 TB01 SIM

1. **确认实验室接入契约**：
   核对[UE 接入与实验室策略](ue-access-policy.zh-CN.md)（`PLMN 460/03`、`DNN oai`、`SST 1`、`5QI 9`、IPv4 地址池 `10.0.0.0/24`）。
2. **为新 UE 添加独立 Open5GS 订阅**：
   在 Spark 上调用 `stacks/open5gs/subscriber.py`，写入一组独立的 IMSI、Ki 和 OPc（初始 `sqn=0`、单数据 PDU、`dnn=oai`、`sst=1`、`five_qi=9`）。禁止多台设备共用同一身份。
3. **烧录 TB01 空白 USIM 卡**：
   按[TB01 SIM 烧录方法](sim-programming-tb01.zh-CN.md)，通过 PC/SC 读卡器以 `T=0` 模式核对卡片 ATR、写入 IMSI/Ki/OPc 与 **Milenage 选择值 `00`**，并确认读回校验和本地 AUTS MAC-S 匹配后再拔卡。

**第 2 步通过标准**：
- Open5GS 核心网已新增该独立订阅且未影响原有订阅；
- 卡内 IMSI 读回与本地 AUTS 校验均匹配私密资料；私密文件以 `0700`/`0600` 权限保存在 Git 之外。

---

## 第 3 步 — 部署 Jetson Console 并接入 UE

1. **在载板上装入模组与 SIM 卡并检查网络**：
   将 **Quectel RM520N-GL** 模组与已烧录的 TB01 Nano-SIM 装入 **[Waveshare SIM8262E-M2 5G for Jetson Orin](https://www.waveshare.net/shop/SIM8262E-M2-5G-for-Jetson-Orin.htm)** M.2 扩展板并接好 4 根天线，通过 USB 3.0 连入 **Jetson Orin**；确认 `ModemManager` 已停用且不自启，NetworkManager 保留 Wi-Fi 管理默认路由可用（其他既有默认路由 metric 严格大于 `10`）。
2. **构建、安装并初始化 Jetson Console（`0.6.2`）**：
   按[Jetson Console 安装](setup-ue-jetson.zh-CN.md)完成构建与安装（`make build-jetson-release`、`verify`、`preflight`、`sudo bash deploy/install-jetson.sh`），随后先停止服务、使用 Spark 的管理地址执行 `commission` 并启动：
   ```sh
   sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
   sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py commission \
     --spark-address 192.0.2.20 --wifi-interface auto
   sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py start
   ```
   *(请将示例地址 `192.0.2.20` 替换为实际 Spark 管理地址。)*
3. **通过 SSH 隧道打开 Jetson Console 并执行 Device Setup**：
   在工作站建立隧道：
   ```sh
   ssh -L 8878:127.0.0.1:8878 <user>@<jetson-host>
   ```
   浏览器打开 `http://127.0.0.1:8878` 登录后进入 **Device Setup**，核对预设上下文变更预览并触发安装配置流程。

**第 3 步通过标准**：
- `curl -fsS http://127.0.0.1:8878/api/v1/health` 返回 `ok`；
- **Overview** 页面显示 SIM 就绪、已在 `460/03` 完成 NR SA 注册、获得 `10.0.0.0/24` 内的活动 IPv4 PDU、`management_protected = true`，且数据面探测通过。

---

## 第 4 步 — 端到端联调验收与可选冷重启自连

1. **通过 SSH 隧道检查 Spark Platform**：
   ```sh
   ssh -L 8877:127.0.0.1:8877 <user>@<spark-host>
   ```
   访问 `http://127.0.0.1:8877`，确认 **Overview**、**gNB**、**Core Network** 与 **Devices** 页面均可看到 `127.0.0.1:8879` 实时指标、当前 UE 上下文、活动 PDU 会话及新鲜的 N3/N6/网桥计数。
2. **核验 Jetson 双路径保护**：
   连续两次新鲜数据探测（含公网目标）通过后，普通 IPv4 默认路由切换为蜂窝优先（metric `10`），同时 Wi-Fi 管理链路（metric `5` 回退及 Tailscale/SSH 管理通道）保持可用。
3. **（可选）启用无值守冷重启自连**：
   确认手动入网与启停均稳定后，按[Jetson Console 安装](setup-ue-jetson.zh-CN.md)中的“可选的开机协调”配置 `boot_connect.py` 与 `aoc-v2-jetson-boot.service`，并通过一次真实冷重启完成验收。

---

## 后续阅读

- **平台界面与日常运维**：[Spark Platform 运维](spark-operations.zh-CN.md) 与 [Jetson Console 运维](jetson-operations.zh-CN.md)
- **故障诊断与恢复**：[Spark 故障排查](troubleshooting-bs-spark.zh-CN.md) 与 [Jetson 故障排查](troubleshooting-ue-jetson.zh-CN.md)
- **利用双端预留算力开发自定义 AI 模块**：[双端 AI 定制指南](ai-customization.zh-CN.md)
