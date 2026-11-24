# SIM 开户与 TB01 烧录参考指南

[English](sim-programming-tb01.md)

本文说明如何为 **Jetson Orin + Quectel RM520N-GL** 终端准备 **Open5GS** 订阅与可编程
**5G USIM** 卡，并提供经过实测核验的 **TB01** 卡片 APDU 协议参考。

## 通用可编程 USIM 前置要求

只要写入与 **Open5GS** 一致的参数，任何支持标准 **5G Milenage 算法的可编程 USIM**
（例如上游 [Osmocom pySim](https://downloads.osmocom.org/docs/pysim/master/html/)
支持的通用白卡）均可接入 **OCUDU + Open5GS** 网络：

1. **在 Open5GS 中为每台 UE 创建独立订阅**：
   在 **DGX Spark** 上通过 `stacks/open5gs/subscriber.py` 写入独立的 **IMSI**、**Ki**
   与 **OPc**，初始 `sqn=0`、单 IPv4 数据 PDU、`dnn=oai`、`sst=1`、`five_qi=9`
   （需与[UE 接入与实验室策略](ue-access-policy.zh-CN.md)对齐）。禁止多台终端共用同一 IMSI。
2. **将订阅密钥保存在 Git 之外**：
   `sim.json`、身份导出文件与备份应存放在仓库之外的受限本地目录（目录 `0700`、文件 `0600`）。
   若输入资料提供的是 `OPc`，切勿把它当成 `OP` 重新派生计算。
3. **写入一致的 USIM 鉴权资料**：
   在 Linux 或 macOS 工作站上通过 PC/SC 读卡器向卡内 `ADF.USIM` 写入匹配的 `EF.IMSI`
   （`6F07`）、`Ki`、`OPc` 及 **Milenage** 算法配置，完成 IMSI 读回与本地 AUTS 校验后，
   再上卡验证 5G SA 注册与首次 SQN 同步。

---

## 已验证硬件参考：TB01 实验白卡规范

以下章节给出针对 **TB01** 实验白卡（基于 `GRSIMWrite 4.4.9+` 离线分析，`GRSIMWrite.exe`
SHA-256 为 `ed4912990f5a2bd5dcbf38df9743d3028a842d2b7ac5594b9825c0627eb48fe5`）
核验通过的协议细节。不同批次固件或其他型号卡的兼容性未在此范围；厂商写卡适配器保存在
本地私有工作区，不随本仓库分发。

### 卡识别与 PC/SC 传输参数

- **参考工具链**：Python `3.12`、`pyscard 2.3.1` 与 Osmocom `pySim`（参考提交 `9aa8934da2415b161eb9726adad2ba7b4f35d1a7`）。
- **传输协议**：独占打开系统 PC/SC 读卡器，并在**首次建立连接时显式指定 `T=0`**（不进行 `T=0`/`T=1` 自动协商，也不回退 `T=1`）。
- **目标 ATR**：`3B9E94801FC78031E073FE211366425454423031DB`。

### SADM 与标准 ADM 的区别

TB01 厂商权限校验通过专用 APDU（`00 FB FF FF 08`）传入由 16 位十六进制字符解码得到的
8 字节 **SADM**。它与标准 `ADM1` 或修改 ADM 命令互相独立，且单条校验返回 `9000` 并不
代表对所有 EF 文件具有无限制写权限。SADM 原文、默认 ADM 及厂商固定前缀严禁进入 Git 或
文档；遇到权限拒绝时禁止盲目穷举 ADM 重试次数。

### 推荐烧录顺序

1. **先只读核对 Open5GS 订阅**：确认待写入的 IMSI、Ki、OPc、AMF、OPc 模式、启用状态及目标 DNN/SST 与现网 Open5GS 订阅一致，不改动其他在线订阅或已有 SQN。
2. **预检与只读备份**：要求系统中仅连接一个 PC/SC 读卡器、独占 `T=0` 连接且完整 ATR 精确匹配。经 `MF` / `EF.DIR` 定位 USIM 应用，私密备份 `ICCID`、`EF.IMSI` 与 `EF.AD`，核对目标 MNC 长度（`460/03` 对应长度 `2`），并拒绝误覆盖其他已上线 UE 的 IMSI。
3. **权限校验后先写 `EF.IMSI`**：选择 `MF` 并完成厂商 SADM 校验（`9000`），进入 `ADF.USIM` 下的 `EF.IMSI`（`6F07`），使用 `pySim.utils.enc_imsi` 编码为 9 字节后执行 `UPDATE BINARY` 并立即读回对比。若被拒绝则立即中止，不在写密钥阶段继续写入。
4. **写入 USIM 鉴权资料（`Ki`、`OPc`、Milenage）**：返回 `MF` 按下表模板写入 `Ki`、`OPc` 与算法选择。不执行格式化、擦除、`EF.DIR` 重建或修改 `ICCID` / `PIN` / `PUK` / `ADM`；仅在 MNC 长度不一致时修改 `EF.AD` 第 4 字节低半字节。
5. **清理禁用网表中的目标条目（按需）**：若复用旧实验卡且 `EF.FPLMN` 含目标实验 PLMN，仅清除对应的 3 字节条目，保留其余字节不变。
6. **重连卡片与本地 AKA 验证**：检查 `IMSI` 持久化与 `ICCID` 保留后，以目标 `Ki`、`OPc`、随机 `RAND` 与初始 `SQN 0` 发起本地 3G AKA 向量测试，核对返回 `AUTS`（`DC 0E ...`）在 `AMF=0000` 下的 MAC-S 有效。最终入网与 SQN 同步须在卡插入 Jetson RM520N-GL 后完成实机验证。

### 已核验 TB01 APDU 命令布局

尖括号表示私密参数；各命令的厂商固定前缀互相独立，不可混用。`Ki` 与 `OPc` 均从 32 位十六进制字符解码为 16 字节。

| 操作 | APDU 布局 | 说明 |
| --- | --- | --- |
| 厂商 SADM 校验 | `00 FB FF FF 08 <SADM:8 bytes>` | 保护写入前必须先执行 |
| USIM IMSI（`EF.IMSI`） | `00 D6 00 00 09 <encoded IMSI:9 bytes>` | 在 `ADF.USIM`（`6F07`）上下文执行 |
| USIM Ki | `00 FB 00 00 18 <fixed prefix:8 bytes> <Ki:16 bytes>` | 在 `MF` 上下文执行 |
| USIM OPc | `00 FB 00 10 19 <fixed prefix:8 bytes> 01 <OPc:16 bytes>` | 其中的 `01` 为 OPc 命令固定字段，非算法选择值 |
| USIM Milenage 选择 | `00 FB 00 00 09 <fixed prefix:8 bytes> 00` | `00` = **Milenage**；`01` = **XOR** |

> [!CAUTION]
> **Milenage 选择值（`00` 与 `01`）**：对 `GRSIMWrite.exe` 的离线逆向确认
> `RadLTE_MLG` 对应 `00`（Milenage）、`RadLTE_XOR` 对应 `01`（XOR）。若误写为
> `01`，即使 `IMSI`、`Ki`、`OPc` 写入均返回 `9000`，`AUTHENTICATE` 仍会报 `9862`
> （MAC 错误）。

### 响应处理与防重放保护

- **`61xx`**：表示仍有待取回字节，应按长度发起有界 `GET RESPONSE`（例如收到 `6110` 后取回即得 `9000` 与 `AUTS` 数据）。
- **禁止自动重试**：收到 `6Cxx`、`63Cx` 重试计数提示、超时或不确定响应时立即停止并保留现场，严禁自动重试写卡或尝试其他管理密钥。
- **持久化防重放日志**：每次执行前先将操作落盘并 `fsync` 到操作账本，任务完成后拒绝同路径重复写入，防止误覆写其他卡片或耗尽卡内计数器。

## 参考资料

- [Osmocom pySim 文档](https://downloads.osmocom.org/docs/pysim/master/html/)
- [pySim PC/SC 实现](https://raw.githubusercontent.com/osmocom/pysim/master/pySim/transport/pcsc.py)
- [ETSI TS 102 221：UICC 接口与管理访问](https://www.etsi.org/deliver/etsi_ts/102200_102299/102221/18.02.00_60/ts_102221v180200p.pdf)
- [ETSI TS 35.208：Milenage 测试数据](https://www.etsi.org/deliver/etsi_ts/135200_135299/135208/18.00.00_60/ts_135208v180000p.pdf)
