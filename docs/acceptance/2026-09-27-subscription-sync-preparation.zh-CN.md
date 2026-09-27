# 订阅同步执行准备 — 2026-09-27

[English](2026-09-27-subscription-sync-preparation.md)

源码基线：`39dde4d0216dee973ed6cbf40ecb500e83c1ac74`，包含本次未提交的工具修改。
应用仍为 Jetson 0.5.1 / Spark 0.2.0。本记录保留执行准备阶段的证据；生产导入和
双设备结果另见[执行记录](2026-09-27-subscription-sync.zh-CN.md)。不关闭任何路线图 Gate。

## 问题、调用路径与影响

问题：如何将 OAI 全部四条已配置订阅补入独立 Open5GS 库，同时保持已有订阅和
独立 SQN？仓库无 CodeGraph 索引。可选维护路径为
`sync-subscriptions.py → MySQL 只读查询 → subscriber.document → 目标差异检查
→ subscriber.insert_script → canonical EJSON 回读`。

用户已授权同步全部已配置订阅，保留目标记录并沿用 OCUDU 单数据策略。静态
IMSI/K/OPc/AMF 仅在 Spark 内存中转换；不导入源 SQN、IMS、固定地址或活动注册/
会话上下文。任何已有静态鉴权冲突都会在写订阅前阻止整个批次。已有记录的 SQN
和策略必须在 EJSON 对象层面完整保持。

`deploy/maintenance/sync-subscriptions.py --check-source` 只读检查源库归属、静态
材料和接入/数据策略是否存在。`--apply` 要求 root，获取已有维护锁，校验当前受保护
部署包、固定 MongoDB 镜像和已有卷；拒绝目标服务/容器正在运行或网络重叠的状态。
工具不使用历史空库初始化入口，该入口不适用于现有生产卷。

工具先备份停机数据库的完整数据卷，读取整个 gzip 流及归档目录校验，并记录
SHA-256，再只启动 MongoDB。本轮尚未演练该完整备份的恢复。插入前还保存规范
EJSON 订阅快照和私有批次身份清单；拒绝意外空库或缺少 IMSI 唯一索引。逐条记录
插入确认，最终检查全部旧记录和新文档。不使用 update/upsert，不自动回滚。

结束时仅停止并移除本次启动的 MongoDB 容器，移除空的自有网络，保留数据库卷。
错误时保留私有备份、批次与结果供检查，不可盲目重试。结果不确定时，应先比较
批次中的新增身份与目标实际内容再决定是否删除。整卷恢复必须在数据库停止、
明确选择恢复后进行，不能覆盖后来已推进的 SQN。

私有输出位于 `/var/lib/aoc-maintenance/subscription-sync-<time>/`，目录 0700、
文件 0600。数据库诊断与 SIM 材料不输出，也不复制到开发电脑。源库仅执行只读
事务；不引入长期跨栈依赖或新的 sudo 规则。

## 发现并修正的 BSON 问题

首次隔离 MongoDB 实测发现，现有导入器默认以 relaxed 模式解析 EJSON，导致
包含 `$numberLong` 的初始 SQN 零实际存成 int32。现已改为
`EJSON.parse(..., {relaxed: false})`，且回读必须满足 `_bsontype === 'Long'`。
该修复只影响新插入记录，不重写已有 SQN。

## 验证与当前边界

- 新增 12 项测试，覆盖原 SQN/策略保留、静态冲突、重复身份、不支持的源策略、
  BSON 类型回读、私有备份、核心网运行时拒绝和命令诊断脱敏。原有 5 项订阅测试
  也通过，并加强了 BSON 解析及回读断言。
- 最后 BSON 修正前，`make ci VENV=local/bootstrap-check` 通过：256 项通过、
  1 项已有 macOS 跳过，两个生产前端构建和仓库审计通过。修正后再次运行全部
  146 项根级协议栈测试通过。本地为 Python 3.11.15 / Node 24.14.0，不代表目标
  发布矩阵已验证。
- Spark Python 3.12.3、固定 MongoDB 镜像上的修正后隔离实测通过：1 条原始
  合成订阅保留 int64 SQN 42，新增 3 条，完整回读一致，新 SQN 为 int64 零，重复
  规划为空，重复插入被拒绝。使用 `network=none`、tmpfs 和合成凭据，没有挂载
  生产卷，临时容器已移除。
- 已暂存工具的实机 `--check-source` 返回四条有效订阅、零变更；身份和密钥不输出。

已审阅的两个文件位于 Spark 的 `~/aoc-ops/subscription-sync-20260927/`。
在 Spark 已认证终端执行：

```sh
sudo /usr/bin/python3 -I "$HOME/aoc-ops/subscription-sync-20260927/sync-subscriptions.py" \
  --apply --expected-source-count 4
```

该命令执行已授权的备份、导入和数据库清理，不切换无线平台，也不启动 Jetson。
当前 SSH 账户仅有固定启停免密 sudo，没有通用免密 sudo 或数据库导入入口，因此
代理无法无人值守执行。不要在对话中发送 sudo 密码。成功结果仍需后续的身份对应、
平台切换、逐台及同时注册/PDU/用户面验收。第二台 Jetson 尚未安装 OCUDU 控制器，
破坏性验收前需单独准备其控制和管理路径。
