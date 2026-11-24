# Open5GS 开户与 5G USIM 配卡指南

[English](sim-provisioning.md)

本指南说明如何在 **Open5GS** 中创建独立 UE 订阅，并制备匹配 **Jetson Orin + Quectel RM520N-GL**
入网的 **5G USIM** 实体卡。

## 前置准备

- 任意支持标准 **5G Milenage 算法的可编程 USIM 白卡**（例如上游
  [Osmocom pySim](https://downloads.osmocom.org/docs/pysim/master/html/)
  支持的常见测试卡）。
- 标准 USB CCID/PC/SC 智能卡读卡器（连接至工作站）。
- 与[网络契约与射频基线](reference/network-and-rf-profile.zh-CN.md)匹配的一组独立凭据
  （`IMSI`、`Ki`、`OPc`）。

## 1. 在 Open5GS 中添加独立订阅

每台 UE 必须拥有各自独立的 `IMSI`、`Ki` 与 `OPc`（初始 `sqn=0`）。在 **DGX Spark**
上运行开户脚本写入核心网数据库：

```sh
python3 stacks/open5gs/subscriber.py --help
```

将订阅配置为与[网络契约与射频基线](reference/network-and-rf-profile.zh-CN.md)一致的
单 IPv4 数据 PDU（`PLMN`、`DNN`、`SST`、`5QI`）。禁止多张 SIM 卡或多台终端共用同一 IMSI。

## 2. 烧录并校验 5G USIM

1. 将导出的订阅文件（`sim.json`、身份资料与备份）保存在 Git 之外的受限本地目录
   （目录权限 `0700`，文件权限 `0600`）。
2. 通过 PC/SC 读卡器（使用 `pySim` 或对应卡片的写卡工具）将 `EF.IMSI`、`Ki`、`OPc`
   及 **Milenage** 算法写入卡内；输入为 `OPc` 时直接写入，不将其当作 `OP` 二次派生。
3. 重新读回 `IMSI` 并通过本地 Milenage 向量（`AUTS`）校验后，再将 Nano-SIM 装入
   Jetson Orin 上的 **Waveshare M.2 5G 扩展载板**进行入网联调。

> [!NOTE]
> 若使用 **TB01** 实验白卡，请参阅[硬件与 TB01 附录](reference/hardware-notes.zh-CN.md#tb01-可编程-usim-apdu-协议参考)
> 中经核验的 PC/SC `T=0` 传输要求与 APDU 命令布局。
