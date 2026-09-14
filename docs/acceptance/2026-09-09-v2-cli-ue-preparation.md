# V2 CLI 与 UE 工具准备记录

日期：2026-09-09。提交：待提交。范围：P1-07/P1-08 开发与无射频检查，尚不勾选实机完成。

## 实现与检查

- 独立运行时 `scripts/v2/runtime.py`、打包安装器 `scripts/v2/package.py`；默认 CLI 切换至 V2，旧 CLI 移为历史入口 `scripts/aocctl-v1`。
- 单数据 UE 工具 `scripts/v2/ue.py`，标准库串口访问、USB 发现、C5GREG、独立 CID、私有基线、一次重连、绑定接口的同次双向探测。
- 14 项新增测试通过；全量 `make check` 146 项通过。覆盖凭据保留、归属拒绝、配置篡改、N2 PID/地址匹配、非零停止留证、保留 CID、重复 DNN、CFUN 回读、IMS 非必需及 Wi-Fi 假成功防护。
- Spark 独立编译 B210 探测程序，仅编译未探测；OCUDU 固定提交 `050a2bb72e1d794cd60570d809987c1fcda3e54b`。
- 生产候选包在 Spark 本地生成，保留已有私有数据库凭据及独立 MongoDB 卷。包不含其他平台的脚本或数据库。
- Compose `config --quiet` 通过；OCUDU `--dryrun` 通过，仅为命令行解析，不代表射频或 NG Setup。
- `systemd-analyze verify` 非零：目标安装的 gNB 路径尚不存在，且另一个宿主服务不可读。没有将此结果记录为服务验收通过；安装后仍须验证。
- Spark 用户级 systemd 替身测试通过：`Requires/BindsTo/After` 停止传播、ExecStartPre 失败、停止超时保留 `Result=timeout/ExecMainStatus=9`；临时进程全部退出。记录 `/home/defaultuser/aoc-v2-systemd-check-1788946349227455288.json`，范围为 `user-systemd-substitutes-no-RF`，不替代生产单元测试。
- Jetson 实际只读发现 `/dev/ttyUSB2`、`enx62164330028c`；`at_commands_sent=false`。旧平台仍运行，没有访问串口或修改网络。

## 候选包摘要

- 目录：`/home/defaultuser/agentic-ocudu-work/v2-production-stage-02`
- 发布 ID：`5efae7b12539292d`
- `release.json` SHA256：`e1e76662d09ecbccf7694494dc20975be9b4387d7f8e51435707f4f1ca0112a0`
- 射频审查模板 SHA256：`6567abddb2a0c2753f40b8f40023770d43b176343dc0a12cae5ed0d331948969`
- 独立探测二进制 SHA256：`78ece33c98a0e6bd5455f9b7257437bbf81063af16ce9d76d389cf7b1141e8d0`
- `configuration_reviewed=true`，`rf_accepted=false`。

首个暂存尝试因内部序列号占位符含下划线被拒绝，未安装或运行服务；修复后 stage-02 成功，并补充完整打包测试。stage-01 为未完成私有目录，不用于安装。

## 当前边界

安装需要 Spark 终端 sudo。已发出具体安装命令；不增免密 sudo，不通过 Docker 绕过宿主权限。安装动作不会启动服务。原 gNB 仍为 MainPID 2829454，尚未交接 B210。源码、无射频检查和实际验收分别记录，第一阶段 Gate 保持未完成。
