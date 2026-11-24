# OCUDU 无线协议栈

[English](README.md)

本目录负责 **OCUDU** 源码获取、ARM64 构建、产物摘要记录、gNB 配置生成与健康检查。
当前默认形态为单进程 `CU-CP + CU-UP + DU`，通过 USB 3.0 / UHD 接入 **USRP B210**
（F1 分离与 7.2x O-RU 属于可选扩展，不在默认基线内）。

上游版本固定在 `config/upstreams.json`。请将源码、私有依赖与编译产物放在本仓库之外的
独立构建目录中，且不要复用外部虚拟环境或覆盖系统 `/usr/local` 下的共享 UHD 安装。

## 实现位置

- `scripts/build.py`：拉取固定版本源码，以普通用户完成 ARM64 编译（配合私有 mbedTLS / GTest 包）及无射频测试，输出 `build-result.json`。
- `deploy/spark/stack/runtime.py`：生成单 IPv4 数据 PDU 的无线配置（`n78`、`20 MHz`、`30 kHz` SCS、`1T1R`、`tx_gain=80`、`rx_gain=54`、`cell_cfg.pusch.max_ue_mcs=24`）并核对 B210 与 N2 状态。
- `scripts/probe_b210.cpp`：仅在 B210 空闲（gNB 完全停止）时探测 UHD 序列号与增益范围，不开启射频流。
- `deploy/spark/stack/package.py`：按构建记录打包、校验并提供全新安装入口（安装时不启动服务）。
- `deploy/spark/stack/libexec/aoc-v2-cpu-latency` 与 `deploy/spark/stack/systemd/`：提供 `LimitRTPRIO=99`、`aoc-v2-cpu-latency.service`（`PartOf=aoc-v2-radio.service`）及可选 `realtime.conf.example`；`scripts/spark/enable_radio_json_metrics.py` 负责开启受守护的 `127.0.0.1:8879` JSON 指标端点。

## 构建入口

```sh
python3 stacks/ocudu/scripts/build.py --workspace <private-workspace> --jobs 2
```

systemd 服务编排统一归属 `deploy/spark/stack/systemd/`，本模块不自行启动核心网，
gNB、AMF 与 UPF 地址均来自受保护的站点部署配置。当前基线仅支持单 IPv4 数据 PDU
（`5QI=9`），不包含 IMS、SIP 与 VoNR。

## 验证说明

请先完成无射频编译与配置解析检查，再在维护窗口中核验 B210 USB 3.0 识别、实时线程调度
与 N2 建链稳定性。B210 被 gNB 占用期间严禁运行 `probe-b210`。

参考资料：[OCUDU 安装文档](https://docs.ocudu.org/user_manual/installation/)、[CU/DU 与 B210 示例](https://docs.ocudu.org/tutorials/cu_du_split/)。
