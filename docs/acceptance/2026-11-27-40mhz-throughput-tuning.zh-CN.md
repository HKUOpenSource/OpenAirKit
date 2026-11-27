# 40 MHz 6D1S3U 吞吐优化与 MTU/MSS 对齐验收记录 — 2026-11-27

[English](2026-11-27-40mhz-throughput-tuning.md)

## 范围与环境

- 日期：`2026-11-27`
- 基线源码版本：`18870db`
- 目标发布版本：`1.1.0`
- Spark 目标环境：DGX Spark（ARM64，Ubuntu 24.04 LTS，内核 `7.0.0-1019-nvidia`，USRP B210 USB 3.0 SuperSpeed，OCUDU `26.04` commit `050a2bb`，Open5GS `2.8.0` + MongoDB `8.0`）
- UE 目标环境：两台 Jetson Orin Nano（ARM64，L4T 内核 `5.15.148-tegra`，Quectel RM520N-GL `cdc_ether` ECM 模式，经 `AT+QCFG="usbspeed","311"` 与 `AT+CFUN=1,1` 从 USB 2.0 `480M` 切回 USB 3.0 `5000M`）
- 脱敏说明：本记录已移除 Tailnet 地址、主机名、本地用户名、USRP 序列号、SIM 凭据、Wi-Fi SSID/BSSID 及原始日志。

## 定位的瓶颈与实施改动

1. **空口与 SDR 扩容（`40 MHz`、`6D1S3U`、`sc16`、`qam256`）**：
   - 在 `deploy/spark/stack/runtime.py`、`config/network-contract.json`、`config/network-profile.example.json`、`config/jetson.example.json`、`stacks/open5gs/config.py` 与 `scripts/aoclib/radio.py` 中，将信道带宽由 `20 MHz`（51 PRB、`23.04` MSps、`sc12`、`64/64` UHD 帧）扩展为 `40 MHz`（106 PRB、`46.08` MSps、`sc16`、`256/256` UHD 帧）。
   - 将 5 ms TDD 配比从 `7 DL / 2 UL` 调整为 `6 DL / 3 UL`（`6 DL sym / 4 UL sym`）。
   - 显式配置 `pdsch.mcs_table = "qam256"` 与 `pusch = {"mcs_table": "qam256", "max_ue_mcs": 27}`（解除原 `max_ue_mcs = 24` 截断）。
2. **核心网 MTU、TCP MSS 钳制与签约 AMBR**：
   - 将 Open5GS SMF `mtu` 与 UPF `ogstun` 网卡 MTU 由 `1400` 提升至 `1440`（`stacks/open5gs/compose/render.py`、`stacks/open5gs/compose/runtime.py`），并同步更新 `deploy/maintenance/repair-connectivity-manifest.py` 中的固定哈希。
   - 在 `stacks/open5gs/compose/runtime.py` 的 `table ip aoc_v2` 新增 `forward` mangle 链，对进出 `10.0.0.0/24` 的 TCP SYN 报文双向钳制 MSS 为 `1400`，消除模组 USB 重枚举后网卡默认 `MTU 1500` 导致的公网 PMTUD 黑洞。
   - 在 `apps/jetson-console/backend/aoc_jetson/network.py` 新增 `align_cellular_mtu()`（`<= 1440`），并在 `managed_routes()`（`prepare`/`promote`）中自动收敛蜂窝口 MTU。
   - 将默认签约会话 AMBR 由 `100/200 Mbps` 放宽至 `500/1000 Mbps`（`stacks/open5gs/subscriber.py`、`scripts/aoclib/core.py`、`scripts/aoclib/subscriber.py`），并在现网 MongoDB 同步更新现有订阅记录（不修改 `sqn` 与密钥）。
3. **主机 TCP 与队列 `sysctl` 基线**：
   - 新增 Spark 专用 `deploy/spark/stack/sysctl/99-aoc-v2-throughput.conf`（`bbr` + `fq` + `16 MiB` 缓冲）。
   - 新增 Jetson 专用 `deploy/jetson/sysctl/99-aoc-v2-jetson-throughput.conf`（`16 MiB` 缓冲、`tcp_window_scaling=1`、`tcp_mtu_probing=1`；适配 L4T `5.15.148-tegra` 不包含 `tcp_bbr`/`sch_fq` 模块的限制）。

## 实机性能对比（高 SNR UE）

### 端到端 5G N6 `iperf3`（UE 蜂窝网卡 -> Spark N6 网桥）

| 测试项 | 改造前（`20 MHz`、`7D1S2U`、`UL MCS<=24`、USB 2.0、`cubic`） | 改造后（`40 MHz`、`6D1S3U`、`qam256`、USB 3.0、Spark `bbr+fq`） |
| --- | --- | --- |
| 下行单流 TCP | `58.3 Mbps`（`934` 次重传，`dl_bs` `2.62 MB`，PHY `63 Mbps`） | 稳态 `112–119 Mbps`（含慢启动 10s 均值 `99.2 Mbps`；`0` 重传；`dl_bs` `457–757 KB`；PHY `121 Mbps`，`0%` BLER） |
| 下行 4 流 TCP | — | `116 Mbps`（`0` 重传） |
| 上行单流 TCP | `13.2 Mbps`（PHY `13.8 Mbps`，`400/400` UL 时隙，`UL MCS 24`） | `50.7 Mbps`（PHY `52.4–53.9 Mbps`，`600/600` UL 时隙，`UL MCS 25`，`0%–1%` BLER） |
| 上行 4 流 TCP | — | `50.4 Mbps` |
| 基带实时异常计数 | `0` underflow/overflow/late | `0` underflow/overflow/late |

### 浏览器 Speedtest 实测

- MTU/MSS 对齐前：下行约 40 Mbps / 上行约 10 Mbps，且伴随 `MTU 1500` vs `1440` PMTUD 黑洞导致的 `Socket Error` 卡死。
- 对齐 `MTU 1440` 与 UPF 双向 MSS `1400` 钳制后：**下行 `107.6 Mbps` / 上行 `32.17 Mbps`**，全程无报错卡死。

## 验证、回滚与已知限制

- **本地与干跑校验**：
  - 使用更新后 `runtime.py` 生成的 `40 MHz` 配置在 Spark 实机执行 `gnb --dryrun` 返回 `0`。
  - `test-frontend-behavior`（`7/7`）、`test-jetson-backend`（`112/112`）、`test-spark-backend`（`72` 项运行，`1` 项 Linux peer-cred 跳过）、`test-stack`（`190/190`，其中 `test_connectivity_endpoint_serves_only_small_health_response` 在网络沙盒外执行通过）、`typecheck`、`docs-audit`（`147` 篇文档）、`release-audit`、`license-audit`、`version-audit`（`1.1.0`）与 `shell-check` 全部通过。
- **回滚方式**：现网修改前已将 Spark 原 `runtime.py`、`core/config/smf.json`、`core/runtime.py`、`core/bundle.json` 与 `release.json` 完整备份至 `/var/lib/agentic-ocudu/v2/`，恢复原文件并重启 `core` 与 `radio` 即可回退；`sysctl` 为独立 `/etc/sysctl.d/` 文件，可直接删除恢复。
- **已知限制**：
  - 第二台 UE 当前处于弱信号摆位（`CQI 5–6`），本轮未调整天线以复测双 UE 并发满载上限。
  - 公网 Speedtest 上限受限于 Spark 上游回传出口（实测 Spark 通过 2.4 GHz Wi-Fi 直连公网单流 HTTP 下载约为 45 Mbps）。
