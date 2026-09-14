# V2 核心网启动与策略依赖修复

日期：2026-09-09。工作树基线提交：`88a4b4d074712662b1cef66fd152ffcf04e59167`；本次变更尚未提交。生产安装与 UE 数据接入仍待验收。

## 已确认的失败原因

通过 Spark 的 `journalctl -u aoc-v2-core.service` 直接读取到两次最新失败均为 `All eleven core services must be healthy`。已暂存初版生产包的运行时 SHA256 为 `ac62dc3761780ceb2295baecc65c5fedac79252d2e401491a4128be7a4663ee8`，其中固定要求 11 个容器。旧补丁删除 PCF 后仅有 10 个服务。此前清理 orphan 的诊断不足，未解决运行时检查与配置不一致的问题。

固定镜像中 `/src/open5gs` 的源代码进一步确认：

- `src/smf/nudm-handler.c:487` 发送 `npcf-smpolicycontrol` 创建请求；`src/smf/gsm-sm.c` 等待策略关联响应。
- `src/pcf/nudr-handler.c:216` 在取得会话策略数据后请求 `nbsf-management` 注册绑定。
- `configs/open5gs/bsf.yaml.in` 提供 BSF 的 SBI/NRF 配置；镜像存在可执行的 `open5gs-bsfd`。
- `configs/open5gs/pcf.yaml.in` 的内联策略示例将 ARP 放在 QoS 内。此前补丁的内联策略形状不正确，不能作为有效修复。

因此撤销“单数据业务无需 PCF”的假设，恢复 PCF 并补齐 BSF。源码证据支持修复方向，但本次没有以空库测试冒充真实 PDU 建立验证。

## 实现范围

健康检查按 Compose 的服务集合逐项验证，拒绝缺失、多余、重复、不健康或空集合，错误包含对应服务。PCF/BSF 使用 NRF 发现，PCF 复用本项目已有数据库连接和订阅策略；撤销 SMF 的直接 PCF 配置和内联 SUPI 策略。启动依赖为 BSF 就绪后 PCF、PCF 就绪后 SMF。

`repair_core.py` 仅在 V2 停止且无遗留容器时安装，使用共同生命周期锁。安装前验证原发布及核心网清单，备份所有本次修改文件；只更新这些文件的摘要。失败自动回滚，主动回滚先校验安装后文件未被再次修改。不更改镜像、数据库卷、凭据、SIM/SQN、无线配置或其他平台。

旧 `patch_pcf.py` 入口改为明确拒绝操作，避免再次删除 PCF。

## 已通过验证

- 23 项相关单元测试：精确服务集合（10/11/12）、错误状态、发布完整性、修复范围、凭据/卷保持、安装失败回滚、主动回滚、活跃服务拒绝安装等。
- Spark 临时项目 `aoc-v2-corecheck-policy-01`，测试网段 `172.28.82.0/24`，空库且无 gNB/UE。生产测试 SIM 数据库未使用。
- 12 个服务全部健康；AMF、SMF、AUSF、UDM、UDR、PCF、NSSF、BSF 均有 NRF 注册证据；SMF/UPF 的 PFCP 关联通过。
- UPF 容器内源地址 `10.0.0.1` 到 ext-DN 的 NAT、ping 和同次双向 iperf3 通过，限速 10 Mbps，接收约 10.123/10.133 Mbps。这不是 UE 性能数据，也不经过 RAN/GTP-U。
- 正常停止全部退出码 0，无 OOM；重建后数据库验证标记仍在。最终测试容器、网桥、临时卷均清理。

远端脱敏结果：`/home/defaultuser/agentic-ocudu-work/v2-policy-repair-01/test-evidence/result.json`。测试 bundle SHA256：`c7cd065d270c00b223aca206f256de7fb46d4be661b64e48a574a19457714bf6`。镜像保持已锁定的 Open5GS、MongoDB 和独立 N6 产物。

## 暂存与待办

修复包已暂存 `/home/defaultuser/agentic-ocudu-work/v2-policy-repair-01`，本地/远端逐文件 SHA256 一致：

| 文件 | SHA256 |
| --- | --- |
| `repair_core.py` | `a80c3e3f0a08d6423b1951b08783f07b3d1b60772148855b974b8bba881a9163` |
| `runtime.py` | `b3923955ba56ee878bd4da950f13ab99af563d7db21aece08f9faad3fdfa553a` |
| `core-runtime.py` | `c8efa0d04c1e399cd204c1f32a1a9f49f223802c6ed6051a5740380fb46dd567` |
| `payload.json` | `e78c6e02b533d4cc9502dd664e51bb6eed201718256bbf0e11a42acb6c9fe4a8` |

- [x] Spark 终端 sudo 安装，保存安装备份路径和生产配置摘要。完成：2026-09-09｜备份：`/var/lib/agentic-ocudu/v2/policy-repair-1788955914466338839`｜修复运行时 SHA256：`b3923955ba56ee878bd4da950f13ab99af563d7db21aece08f9faad3fdfa553a`。
- [x] 生产核心网与 OCUDU 启动，确认当前调用周期的 N2/NG Setup。完成：2026-09-09｜启动记录：`starting` → `n2-ready`｜gNB PID：`2740945`。UE 尚未接入时不将此项扩大解释为数据 PDU 通过。
- [x] Jetson 注册并取得真实 `10.0.0.0/24` 数据地址，验证 PCF/BSF 会话处理不再崩溃。完成：2026-09-09｜数据 CID `1`、地址 `10.0.0.2`、`registered_5gs=true`、`pdu_active=true`、`pool_valid=true`。
- [x] 真实 UE 同次双向传输。完成：2026-09-09｜接口 `enx62164330028c`、源地址 `192.168.225.29`、路径经 `172.28.81.15`；上行 `5.761741 Mbps`、下行 `25.704490 Mbps`、方向衔接等待 `3s`、`passed=true`。QoS、故障恢复及第一阶段其余门槛仍待验证。

本次完成后生产 V2 服务仍为停止/失败状态，无主进程或控制进程；不新增固定时长观察任务。
