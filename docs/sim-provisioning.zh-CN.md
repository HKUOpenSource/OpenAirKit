# Open5GS 开户与 5G USIM 烧录指南

[English](sim-provisioning.md)

本指南说明如何在 **Open5GS** 核心网中添加独立 UE 用户订阅，并完成匹配 **Jetson Orin +
Quectel RM520N-GL** 入网鉴权的 **可编程 5G USIM 卡** 烧录与校验。

## 前置条件

- 支持标准 **5G Milenage 算法的可编程 5G USIM 卡**（例如上游
  [Osmocom pySim](https://downloads.osmocom.org/docs/pysim/master/html/)
  所支持的测试卡）。
- 连接至烧录工作站的标准 USB CCID/PC/SC 智能卡读卡器。
- 与[网络契约与射频基线](reference/network-and-rf-profile.zh-CN.md)匹配的一组独立订阅凭据
  （`IMSI`、`Ki`、`OPc`）。

## 1. 在 Open5GS 中添加独立订阅

每台终端须独占独立的 `IMSI`、`Ki` 与 `OPc`（初始 `sqn=0`）。在 **DGX Spark** 上运行
开户脚本写入核心网数据库：

```sh
python3 stacks/open5gs/subscriber.py --help
```

将该订阅配置为与[网络契约与射频基线](reference/network-and-rf-profile.zh-CN.md)一致的
单 `IPv4` 数据 PDU（`PLMN`、`DNN`、`SST`、`5QI`）。严禁多张 USIM 卡或多台 UE 共用同一
用户标识。

## 2. 烧录并校验 5G USIM

1. 将导出的订阅清单（`sim.json`、身份资料与备份）保存在 Git 之外的受限本地目录
   （目录权限 `0700`，文件权限 `0600`）。
2. 通过 PC/SC 读卡器（使用 `pySim` 或卡商配套工具）写入 `EF.IMSI`、`Ki`、`OPc` 及
   **Milenage** 算法；传入 `OPc` 时直接写入原值，切勿按 `OP` 进行二次派生。
3. 回读确认 `EF.IMSI` 持久化写入无误并完成本地 Milenage 鉴权向量（`AUTS`）校验后，
   再将 Nano-SIM 装入 Jetson Orin 上的 **Waveshare M.2 5G 扩展载板**开展装卡实机验证。

> [!NOTE]
> 若使用 **TB01** 未烧录 5G USIM 测试卡，请严格遵照[硬件与 TB01 附录](reference/hardware-notes.zh-CN.md#tb01-可编程-usim-apdu-协议参考)
> 中经实机核验的 PC/SC `T=0` 传输要求与 APDU 指令布局。
