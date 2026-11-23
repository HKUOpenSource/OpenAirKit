# Spark 与 UE 运行时对齐验收 — 2026-11-23

[English](2026-11-23-spark-ue-alignment.md)

## 范围与源码基线

- 源码基线：`5ff2b244df05f60dea0c570b27a92dcd956f4fff` 及分支
  `fix/align-spark-ue-runtime` 上的对齐提交 `a5965c7`。
- Spark 目标机：DGX Spark（ARM64、Ubuntu 24.04.5 LTS、内核 `7.0.0-1019-nvidia`、
  Python 3.12.3、Docker 29.6.2、USB 3 SuperSpeed 连接 USRP B210），Open5GS 2.8.0 +
  MongoDB 8.0.30 与本地 `127.0.0.1:8000–8002` 共驻推理服务并行运行。
- UE 目标机：Jetson Orin Nano（ARM64、Ubuntu 22.04.5 LTS、JetPack 6.2 / L4T、
  Python 3.10.12、Quectel RM520N-GL 运行 `cdc_ether` ECM 模式，数据接口位于 USB `0a`，
  串口位于 `00..03`）。
- 本文已脱敏，不含 Tailnet 地址、SIM 标识、凭据、B210 序列号及原始日志。

## 打包与审批产物

| 产物 | Release / ID | 归档或清单 SHA-256 |
| --- | --- | --- |
| Spark Platform `0.2.1` | `599a67f4c4bfd503` | 归档 `a0d309e53140c79251a2a24305be9f86aadfbc28bd1f7b86ce8b84a533dedb97` |
| Spark 维护审批包 | `spark` | `fa3af457ea98078dd08173abad4f6d26ea395763111b60884f19150bdb73e415` |
| Jetson Console `0.6.2` | `18b45ddf1164a8ba` | 清单 `52a7702a7c33edeafcd55da32c2f13477ee2b5f943edc4aedbc112c6b87caef1`；归档 `a5dd24472ba49016a01540d05010a90e6bb6158cac865f5efc84a5768dd34d5f` |
| Jetson 维护审批包 | `jetson` | `a39a014fa4d8a6bee4f9a41f62ec243018813bd67406845d7eeab2e10a9bf764` |

两次离线包均在对齐提交完成前基于分支改动构建（manifest 标记 `dirty=true`）。

## 已实施的代码与配置对齐

1. **Open5GS MongoDB 内核适配（`stacks/open5gs/compose/render.py`）**：
   为 `mongo` 服务默认写入 `GLIBC_TUNABLES=glibc.pthread.rseq=1`，适配 Linux 7.0+ 内核并补充单测。
2. **Spark 协议栈射频与低时延持久化（`deploy/spark/stack/`）**：
   将 `rx_gain=54` 与 `cell_cfg.pusch.max_ue_mcs=24` 写入 `runtime.py`，新增
   `libexec/aoc-v2-cpu-latency`、`systemd/aoc-v2-cpu-latency.service`、`cpu-latency.conf`
   与 `realtime.conf.example`。
3. **Spark 指标端口迁移（`8001 -> 8879`）**：更新
   `apps/spark-platform/backend/aoc_spark/telemetry.py` 与
   `scripts/spark/enable_radio_json_metrics.py`（支持从 `8001` 迁出，并在 `remove_guard()`
   删表前先停止 `aoc-v2-metrics-guard.service`）。
4. **Jetson ECM（`0a` + `00..03`）发现与安装器 `umask` 修复**：在
   `apps/jetson-console/backend/aoc_jetson/hardware.py` 增加 `("0a", ("00", "01", "02", "03")): "02"`；
   在 `deploy/jetson/manage.py` 中对 `venv` 创建/`pip install` 临时应用 `os.umask(0o022)`，并在
   `private_write()` 显式调用 `os.chmod(temporary, mode)`。

## 实机部署与联合验证结果

- **Spark 端（`spark-75c3`）**：
  - 安装 `/usr/local/sbin/aoc-maintain` 并将 Monitor 升级至 `599a67f4c4bfd503`，`aoc-v2-core.service` 全程未中断。
  - 首次尝试整文件覆盖 `/opt/agentic-ocudu/v2/runtime.py` 时因实机保留 schema 2 目录（`units/` 与历史备份）触发 `Unlisted release files`，事务自动完整回滚且未影响核心网。
  - 改为就地精准修补实机 `runtime.py`（`6aa11528...` -> `f1d7c2a2...`）后移除临时 `/run/systemd/system/aoc-v2-radio.service.d/90-rx-gain-test.conf`，将 `aoc-v2-metrics-guard` 迁至 `127.0.0.1:8879`，并通过 `gnb --dryrun` 后重启 `aoc-v2-radio.service` 与 `aoc-observe.service`。
  - 最终只读复核：7 个自有服务全部 `active`（`NRestarts=0`）、`127.0.0.1:8877/api/v1/health` 返回 `{"status":"ok","collector":"ok"}`、`127.0.0.1:8879` 已 `LISTEN` 并与采集器建立 `ESTAB` 连接、`8000–8002` 共驻容器不受影响、AMF N2 `setup_success: true`、gNB 日志持续显示 UE 正常通信（`CQI 15`、`DL MCS 26–27`、`UL MCS 24`、`0% BLER`）。
- **UE 端（`zihao-desktop`）**：
  - 停止并禁用冲突的旧控制台服务（保留其目录供回滚），对齐 `at_interface_number="02"`，更新维护审批后安装 `18b45ddf1164a8ba`，并修正在 `umask 077` 下暴露的 `venv`/`web.json`/`boot-ready.conf` 目录权限。
  - 安装 `/opt/agentic-ocudu/jetson/boot_connect.py` 并完成 ECM 只读 AT/SIM/配置/USB 速率兼容性预检；在安装后生成 `/etc/aoc-v2-jetson/boot.json`，写入 `boot-ready.conf` 与 `aoc-v2-jetson-boot.service`，并启用 `web`、`device`、`boot` 三个单元开机自启。
  - 随 `aoc-maintain start` 实测 `boot_connect.py ready`、`site_guard.py`（`ttyUSB2`）与 `network_entry.py` 均一次通过；最终检查 `aoc-v2-jetson-web` 与 `aoc-v2-jetson-device` 均为 `active (running)`（`NRestarts=0`），`127.0.0.1:8878/api/v1/health` 返回 `{"status":"ok","web":"ok","device":"ok"}`，`aoc-maintain ue-status` 汇报 `quality="ok"`、`connected=true`、`registered=true`、`data_session_active=true`、`lab_policy_match=true`、`management_protected=true`（`maintenance=false`、`recovery_paused=true`）。

## 实机冷重启验证与网关探测限速修复

- 首次实机无值守冷重启触发了 `aoc-v2-jetson-boot.service`（`boot_connect.py ready`
  与 `connect`），在 USB ECM 网卡冷启重命名（`cdc_ether`、`480 Mbps`）与 AT 串口下完成：
  `readiness`（`28.5 s`）、`identity_and_registration`（`32.6 s`，
  `configuration_differences: []`，约 `4.6 s` 完成 `NR5G` 注册）及 `standard_setup`
  建链任务派发（`37.2 s`）。最终 `aoc-v2-jetson-web`、`aoc-v2-jetson-device`（重启次数
  `0`）、`/api/v1/health`、IPv4 蜂窝默认路由（跃点数 `10` 优于 Wi-Fi `30000`）与
  Spark gNB 调度（`CQI 15`、`DL MCS 27`、`UL MCS 24`、`PUSCH SINR ~30 dB`、`0%` 误块率）均正常就绪。
- `standard_setup` 阶段暴露问题：`NetworkManager` 显示管理 Wi-Fi 与管理隧道全程持续在线，
  但 `boot_connect.py` 因每 3–4 秒单包 `ping -c 1 -W 2` 丢包一次而抛出
  `ValueError: Management gateway unreachable` 中止；实测网关 ICMP 丢包率达
  `66.7%`，确认为校园网网关 ICMP 限速所致。
- `677b1cc` 之后补充修复：`deploy/jetson/boot_connect.py` 在单包探测失败后使用间隔探测
  `ping -c 3 -i 1 -W 2` 重试，成功结果按 `GATEWAY_CACHE_SECONDS = 15.0` 缓存，同时保留每次调用的
  `inspect_management` 与 `nmcli` 校验，并在 `wait_ready`、`connect` 进入维护态前与
  `Serial.select_once` 边界强制清缓存重探；`tests/test_jetson_boot.py` 新增
  `ManagementTests` 单元测试。

## 回归测试与遗留待测项

- 在分支提交 `a5965c7` 完成基线验证：`test-frontend-behavior`（7/7）、
  `test-jetson-backend`（109/109）、`test-spark-backend`（72 项运行、1 项 Linux
  对端凭据测试按平台跳过）、`test-stack`（192/192，含回环 HTTP 沙箱外验证）、
  `typecheck`、`docs-audit`、`release-audit`、`license-audit` 与 `shell-check` 全部通过；
  `boot_connect.py` 与文档更新后已重跑 `test-jetson-boot`、`test-stack` 及全部审计项。
- 遗留实机验证项：将更新后的 `boot_connect.py` 安装到 Jetson 主机后，仍需执行一次复测冷重启确认
  `boot_connect.py` 终态写为 `status="completed"`；路线图中的 `V2-P3-15`、
  `V2-P3-17`、`V2-P3-GATE` 与 `V2-R06` 暂保持未勾选。
