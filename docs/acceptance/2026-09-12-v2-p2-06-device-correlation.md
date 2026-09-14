# V2 P2-06 设备关联验收记录

日期：2026-09-12
任务：V2-P2-06

## 关联规则

- AMF 与 SMF 只在同一次采集中按完整 SUPI 关联；完整值只存在于适配器局部变量，输出为 SHA-256 截断 ID 和末四位。
- AMF/SMF 容器 StartedAt 组合成核心网运行周期。设备保留稳定脱敏 ID，同时记录 epoch，使重启前后的状态证据可区分。
- 同一响应出现重复 SUPI 时拒绝该身份，不拼接会话。不同 SUPI 复用同一组 gNB/AMF/RAN NGAP 标识时保留两个设备，但清空冲突标识并标记 `ambiguous_ngap_identifiers`。
- RNTI/PCI/DU UE ID 形成独立 `radio_only` context。当前没有 RNTI 到 SUPI 的权威映射，所以绝不与订阅设备合并。
- scheduler 临时标识按 gNB InvocationID、观测间隔和 DU UE ID 变化分代；日志 reader 按 inode/epoch 处理轮转。
- infoAPI 每轮是当前视图。设备消失或接口断流后不沿用为当前在线；数据库中的最后记录仅作为 stale 历史显示。
- 平台不读取 MongoDB 订阅表来推断在线，订阅配置不进入当前设备列表。

## 页面

设备详情显示证据来源、关联依据、首次/最近观测、注册层、无线层、数据 PDU，以及 QFI/5QI 和经过白名单核对的 N3 端点状态。无线 context 和订阅设备仍分别列出。

## 验证

后端 30 项测试通过，覆盖 SUPI 脱敏、AMF/SMF 精确关联、重复 SUPI、NGAP 标识冲突、进程分代、RNTI/DU ID 复用、日志增量/轮转和 stale 历史；前端 production build 与 `git diff --check` 通过。
