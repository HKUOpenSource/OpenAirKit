# 硬件、模组 USB 拓扑与 TB01 附录

[English](hardware-notes.md)

本附录集中收录 **Quectel RM520N-GL** USB 接口拓扑映射、QMAP 固件诊断命令、
Linux 内核兼容性说明及 **TB01** 可编程 5G USIM 卡的 APDU 协议规范。

## Quectel RM520N-GL USB 接口布局

将 **Quectel RM520N-GL** 安装于 **Waveshare SIM8262E-M2 5G for Jetson Orin**
扩展载板并通过 USB 3.0 接入 Jetson 后，模组将枚举为 **RNDIS** 或 **ECM（`cdc_ether`）**
拓扑。Jetson Console 在打开任何串口前均会校验 USB 接口描述符并拒绝不匹配配置（不可仅凭
`ttyUSB` 编号判定）：

| USB 数据驱动 | 数据接口 `bInterfaceNumber` | 串口 `bInterfaceNumber`（`DIAG / GNSS / AT / Modem`） | 所需 `device.at_interface_number` |
| --- | --- | --- | --- |
| `rndis_host`（RNDIS） | `00/01` | `02`、`03`、`04`、`05` | `"04"` |
| `cdc_ether`（ECM） | `04` | `00`、`01`、`02`、`03` | `"02"` |
| `cdc_ether`（ECM） | `0a` | `00`、`01`、`02`、`03` | `"02"` |

若在 RNDIS 与 ECM 模式间切换模组配置，须先停止 Jetson Console 服务并更新
`/etc/aoc-v2-jetson/device.json` 中的 `device.at_interface_number`；若已启用
开机协调器，需同步刷新 `/etc/aoc-v2-jetson/boot.json`。

## RM520N-GL QMAP 与 MPDN 固件核查

在搭载 QMAP 固件的 RM520N-GL 上，主机侧数据转发需要默认 WWAN 与 MPDN 规则准确
绑定至对应数据 profile。Jetson Console 负责配置 `oai` 数据上下文同时保留既有 QMAP
规则。若模组已注册并取得 IPv4 地址但主机无法转发流量，请先停止 `aoc-v2-jetson-device.service`，
对照厂商手册执行以下只读 AT 查询：

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

- **DGX Spark Linux 7.0+ 内核 + MongoDB 8.0**：`stacks/open5gs/compose/render.py` 会自动为 `mongo` 容器注入 `GLIBC_TUNABLES=glibc.pthread.rseq=1`，确保 TCMalloc per-CPU `rseq` 分配在较新 Linux 内核上正常初始化。
- **Jetson 排除 `ModemManager`**：须停止、禁用并屏蔽 `ModemManager.service`，防止其与 `aoc-v2-jetson-device.service` 争抢 RM520N-GL AT 串口。

## TB01 可编程 USIM APDU 协议参考

若使用 **TB01** 未烧录 5G USIM 测试卡（`ATR: 3B9E94801FC78031E073FE211366425454423031DB`），
请通过独占 **PC/SC `T=0`** 会话（`pyscard` + Osmocom `pySim.utils.enc_imsi`）执行下表
经过实机核验的 APDU 指令序列。厂商 SADM、固定前缀、IMSI、Ki 与 OPc 仅允许存放在
Git 之外的受限本地目录（`0700`/`0600`）。

| 操作 | APDU 布局 | 技术说明 |
| --- | --- | --- |
| 厂商 SADM 校验 | `00 FB FF FF 08 <SADM:8 bytes>` | 由 16 位十六进制字符解码为 8 字节；受保护写操作前在 `MF` 下执行 |
| USIM IMSI（`EF.IMSI`） | `00 D6 00 00 09 <encoded IMSI:9 bytes>` | 在 `ADF.USIM` -> `EF.IMSI`（`6F07`）上下文写入并立即回读核对 |
| USIM Ki | `00 FB 00 00 18 <fixed prefix:8 bytes> <Ki:16 bytes>` | 在 `MF` 上下文执行 |
| USIM OPc | `00 FB 00 10 19 <fixed prefix:8 bytes> 01 <OPc:16 bytes>` | 字节 `01` 为 OPc 命令固定字段，并非算法选择位 |
| USIM Milenage 选择 | `00 FB 00 00 09 <fixed prefix:8 bytes> 00` | **`00` = Milenage**，**`01` = XOR**（误设为 `01` 将导致 `AUTHENTICATE` 返回错误 `9862`） |

### 写卡安全约束

- **保留出厂卡片结构**：保留 `ICCID`、`PIN`、`PUK` 与 `ADM`，严禁格式化或重建 `EF.DIR`；仅当目标 MNC 长度不同时（PLMN `460/03` 对应 `2`）修改 `EF.AD` 第 4 字节低半字节。
- **按需清理禁用网络列表**：若复用曾测试过的 USIM 卡且 `EF.FPLMN` 中写入了 `460/03`，仅清除对应 3 字节条目。
- **规范处理 `61xx` 并禁止盲目重试**：遇到 `61xx`（如 `6110`）须通过有界 `GET RESPONSE` 读取后续数据；遇到 `63Cx` 重试计数器告警或未知状态字时应立即中止操作。
- **本地与实机闭环校验**：以目标 `Ki`、`OPc`、随机 `RAND` 与初始 `SQN 0` 完成本地 3G AKA 测试并核验 `AUTS` MAC-S（`AMF=0000`），再装卡在 Jetson 端完成 5G SA 实网入网验证。
