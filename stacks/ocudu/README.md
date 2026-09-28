# OCUDU radio stack

负责 OCUDU 源码获取、ARM64 构建、产物记录、配置生成及 gNB 健康检查。运行形态从单进程 CU-CP + CU-UP + DU 开始，B210 通过 USB3 / UHD 接入；无需 O-RU。F1 分离和 7.2x O-RU 是后续独立选项。

上游版本来自 `config/upstreams.json`；源码、私有依赖和产物进入指定工作目录。构建不得复用外部虚拟环境或覆盖 `/usr/local` 中共享 UHD。Spark 已完成固定提交构建与无射频测试，结果见[验收记录](../../docs/acceptance/2026-09-11-radio-realtime-policy.md)。

## 实现位置

- `scripts/build.py`：已实现固定提交检查、普通用户 ARM64 构建、私有 mbedTLS/GTest 解包和无射频测试，输出 `build-result.json`。
- `deploy/spark/stack/runtime.py`：生成当前单数据 PDU 的无线配置，核对 B210 与当前 N2 建链。
- `scripts/probe_b210.cpp`：只在原 gNB 完全退出后探测 UHD serial 和增益范围，不启动射频流。
- `deploy/spark/stack/package.py`：按固定构建记录打包和验证 ARM64 产物，提供不启动服务的全新安装入口。

Build entry point: `python3 stacks/ocudu/scripts/build.py --workspace <private-workspace> --jobs 2`. It does not install system packages or probe UHD devices. Keep source and build output outside this repository.

systemd 编排统一归属 `deploy/spark/stack/systemd/`，本模块不自行启动核心网。gNB、AMF 和 UPF 地址由受保护的站点配置生成。

The current stack scope is one IPv4 data PDU with 5QI 9. IMS, SIP and VoNR are not part of this independent stack release.

## 验收

先完成无射频构建和配置解析，再在维护窗口确认 B210 序列号、USB3、线程调度和启动稳定性。B210 被占用时不得执行会打开设备的探测或测试。当前 CPU 策略和 xHCI IRQ 预留以实机验收记录为准；不修改全局 IRQ 亲和性，也不设置固定时长连续运行门槛。

参考：[OCUDU 安装](https://docs.ocudu.org/user_manual/installation/)、[CU/DU 与 B210 示例](https://docs.ocudu.org/tutorials/cu_du_split/)。
