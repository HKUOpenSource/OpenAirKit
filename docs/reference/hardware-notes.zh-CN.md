# 硬件、模组 USB 拓扑与 TB01 附录

[English](hardware-notes.md)

本附录集中收录 **Quectel RM520N-GL** 的 USB 接口映射表、QMAP 固件排查命令、
Linux 内核兼容性说明以及 **TB01** 可编程 USIM 卡的 APDU 协议参考。

## Quectel RM520N-GL USB 接口布局

将 **Quectel RM520N-GL** 安装于 **[Waveshare SIM8262E-M2 5G for Jetson Orin](https://www.waveshare.net/shop/SIM8262E-M2-5G-for-Jetson-Orin.htm)**
扩展载板并通过 USB 3.0 接入 Jetson 后，模组会以 **RNDIS** 或 **ECM（`cdc_ether`）**
拓扑枚举。Jetson Console 在打开任何串口前都会校验 USB 描述符（不能仅凭 `ttyUSB` 编号判断）：

| USB 数据驱动 | 数据接口 `bInterfaceNumber` | 串口 `bInterfaceNumber`（`DIAG / GNSS / AT / Modem`） | 所需 `device.at_interface_number` |
| --- | --- | --- | --- |
| `rndis_host`（RNDIS） | `00/01` | `02`、`03`、`04`、`05` | `"04"` |
| `cdc_ether`（ECM） | `04` | `00`、`01`、`02`、`03` | `"02"` |
| `cdc_ether`（ECM） | `0a` | `00`、`01`、`02`、`03` | `"02"` |

若在 RNDIS 与 ECM 模式间切换固件配置，请先停止 Jetson Console 服务并更新
`/etc/aoc-v2-jetson/device.json` 中的 `device.at_interface_number`；若启用了
开机协调器，请同步刷新 `/etc/aoc-v2-jetson/boot.json`。

## RM520N-GL QMAP / MPDN 固件核查

在采用 QMAP 固件的 RM520N-GL 上，主机能获得蜂窝转发能力需要默认 WWAN 与 MPDN
规则关联到对应的数据 profile。Jetson Console 负责配置 `oai` 数据上下文并保留既有 QMAP
规则。若已注册且获得 IPv4 地址仍无法通信，请先停止 `aoc-v2-jetson-device.service`，再执行以下只读 AT 查询对照厂商手册核查：

```text
AT+CGDCONT?
AT+QCFG="usbnet"
AT+QCFG="usbspeed"
AT+QMAP="MPDN_rule"
AT+QMAPWAC?
AT+QNWPREFCFG="nr5g_band"
AT+QNWPREFCFG="nr5g_disable_mode"
AT+QNWPREFCFG="mode_pref"
```

## 主机系统与内核兼容性说明

- **DGX Spark Linux 7.0+ 内核 + MongoDB 8.0**：`stacks/open5gs/compose/render.py` 会自动为 `mongo` 容器注入 `GLIBC_TUNABLES=glibc.pthread.rseq=1`，确保 TCMalloc per-CPU `rseq` 在较新内核上正常初始化。
- **Jetson 禁用 `ModemManager`**：务必停止、禁用并屏蔽 `ModemManager.service`，避免抢占 RM520N-GL AT 串口。

## TB01 可编程 USIM APDU 协议参考

若使用 **TB01** 实验白卡（`ATR: 3B9E94801FC78031E073FE211366425454423031DB`），
请通过独占 **PC/SC `T=0`** 连接（`pyscard` + Osmocom `pySim.utils.enc_imsi`）执行下表
经过核验的指令序列。厂商 SADM、固定前缀、IMSI、Ki 与 OPc 仅存放在 Git 之外的受限本地目录（`0700`/`0600`）。

| 操作 | APDU 布局 | 技术说明 |
| --- | --- | --- |
| 厂商 SADM 校验 | `00 FB FF FF 08 <SADM:8 bytes>` | 由 16 位十六进制字符解码为 8 字节；受保护写入前于 `MF` 下执行 |
| USIM IMSI（`EF.IMSI`） | `00 D6 00 00 09 <encoded IMSI:9 bytes>` | 在 `ADF.USIM` -> `EF.IMSI`（`6F07`）上下文写入并立即读回比对 |
| USIM Ki | `00 FB 00 00 18 <fixed prefix:8 bytes> <Ki:16 bytes>` | 在 `MF` 上下文执行 |
| USIM OPc | `00 FB 00 10 19 <fixed prefix:8 bytes> 01 <OPc:16 bytes>` | 其中的 `01` 为 OPc 命令固定字段，并非算法选择值 |
| USIM Milenage 选择 | `00 FB 00 00 09 <fixed prefix:8 bytes> 00` | **`00` = Milenage**，**`01` = XOR**（误写 `01` 会导致 `AUTHENTICATE` 报错 `9862`） |

### 写卡安全约束

- **保留出厂结构**：保留 `ICCID`、`PIN`、`PUK` 与 `ADM`，不要格式化或重建 `EF.DIR`；仅当目标 MNC 长度不同时（`460/03` 为 `2`）调整 `EF.AD` 第 4 字节低半字节。
- **清理旧卡片禁用网表（按需）**：若复用测试卡且 `EF.FPLMN` 含 `460/03`，仅清除对应 3 字节条目。
- **正确处理 `61xx` 并禁止盲目重试**：遇到 `61xx`（如 `6110`）使用有界 `GET RESPONSE` 读取后续数据；遇到 `63Cx` 重试计数警告或状态不明时立即停止并检查现场。
- **本地与实机闭环校验**：以目标 `Ki`、`OPc`、随机 `RAND` 与初始 `SQN 0` 发起本地 3G AKA 测试并核验 `AUTS` MAC-S（`AMF=0000`），随后上卡完成 Jetson 实机 5G SA 入网验证。
