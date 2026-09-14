# V2-P1-05 独立订阅初始化

日期：2026-09-09。提交：待提交。静态订阅初始化已通过；真实 AKA 与 SQN 重同步未验证，保留到无线验收。

## 验证

1. 以固定 Open5GS 2.8.0 源码 `misc/db/open5gs-dbctl` 和 `lib/dbi/subscription.c` 核验 BSON 模型。SQN 必须为 BSON int64，不能把旧 MySQL 的十六进制字符串直接写入。
2. `stacks/open5gs/subscriber.py` 只接受一份私有静态身份/认证材料和独立身份确认文件。允许输入历史 `sqn` 字段但不使用它，首次初始化新库 SQN=0，后续由当前栈持久化和标准重同步推进。
3. 单 slice SST=1、无 SD，单 DNN `oai`、IPv4、5QI=9；ARP 优先级 8、能力 1/脆弱性 2，AMBR 上行 100 Mbps、下行 200 Mbps。UE 池由 SMF/UPF 配置为 `10.0.0.0/24`，不把订阅存在解释为在线。
4. `network=none` 的 MongoDB 认证测试通过：未认证读取被拒绝；合成订阅插入/回读成功；测试 SQN 推进为 42 后重复导入被拒绝，SQN 仍为 int64 42，订阅数量仍为 1。测试容器正常退出并删除。
5. Spark 本机生成新数据库凭据，认证空库 11 NF 完整启动、停止、持久卷重建和清理再次通过。秘密不跨主机传输、不写入 Git，配置保存在 owner-only bundle 内。
6. 新项目 `aoc-v2-open5gs` 仅启动 MongoDB，使用已有 `0600` 当前测试 SIM 材料及身份确认文件初始化一条新订阅。回读 DNN/IPv4/SST/5QI 成功；未读取或写入旧数据库，未复制旧 SQN。
7. MongoDB 正常退出 0，Compose down 保留 `aoc-v2-open5gs-mongo`；新网桥已删除，没有新 gNB 或核心 NF 运行。原 gNB MainPID `2829454` 保持 active。

## 证据与保留状态

新私有 bundle：Spark `/home/defaultuser/agentic-ocudu-work/open5gs-v2-provision-01`。
新库卷：`aoc-v2-open5gs-mongo`。不要删除或用空库初始化覆盖它。

| 记录 | SHA256 |
| --- | --- |
| 真实单条订阅初始化 `open5gs-v2-provision-evidence-01/result.json` | `94469c0e344eef616fd9081b10705fab3c5aedbcddc537aa531e245c2a29f24c` |
| 合成认证/重复导入 `aoc-v2-subscription-test-01.json` | `d66e7c46b0fe16bafb77d2db0f77b8fbb1459bcb72a24b0e6508cdef1ad80e50` |
| 带认证空库 `aoc-v2-corecheck-evidence-03/result.json` | `bcadcdc3e2c9f7d10e8025d75b124d6b3668bc8e5e0e7110532f6bd40bcf642b` |

实际无线鉴权、SQN 重同步及性能仍待 P1-09/P1-14。初始化成功不等于 UE 注册成功，不允许重复导入旧 SQN 掩盖后续鉴权问题。
