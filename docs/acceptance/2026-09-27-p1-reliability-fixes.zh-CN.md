# 三项 P1 可靠性修复 — 2026-09-27

[English](2026-09-27-p1-reliability-fixes.md)

源码基线：`87e059fd5b4010384606eca6180bd0f3ecc86aa1` 加本轮未提交修改。
应用版本保持 Jetson 0.6.0、Spark 0.2.0。本记录是源码和本地回归证据，
不代表部署或实机验收。
后续打包、设备升级和限时实机检查见[部署记录](2026-09-27-ui-deployment.zh-CN.md)；
以下证据描述最初的源码修复阶段。

## 问题、调用路径与影响

问题：能否处理[开发审阅](2026-09-27-next-round-review.zh-CN.md)中的三条 P1
失败路径，避免模组保持关闭、控制任务失联后持续占用，以及发现外部 Web 监听器前
已修改协议栈？仓库无 CodeGraph 索引，直接检查源码与测试。

- `Agent.execute → Agent.write → Modem.write(cfun0)`：commissioning 和 SIM
  校验通过后，在发送 CFUN=0 前授予一次电源恢复权限。命令交互或回读失败时，
  在调用者仍持有硬件锁的情况下尝试 CFUN=1，即使任务已请求取消。原始错误仍令
  任务失败或取消；恢复失败明确记录，每次 CFUN=1 尝试都会清除临时授权。不重试
  关闭电源，管理或身份检查未通过时不触发补偿。setup 和 recover 两条路径均覆盖。
  若传输或硬件也拒绝补偿命令，不能保证物理电源恢复成功。
- `POST /control → run_control → control_messages → poll_control`：未收到
  终态就发生正常 EOF 时，进入已有的恢复查询路径。仅查询原任务 ID，不重发 run。
  任务未知或执行器不可用时标记 interrupted；已完成任务保留终态。API 释放任务
  预留不等于原 systemd 操作未执行。
- `start.sh → Controller.start → check_web_listener → maintain`：首次变更前
  读取 Web 端口所有 IPv4/IPv6 监听器的内核 cgroup 归属。已有监听器必须全部匹配
  运行中 Web 单元的 `ControlGroup`，且健康接口为 OK。外部/未知归属或检查失败时
  零变更退出，自有健康监听器允许幂等启动。此检查不预留 socket，也不锁住检查后
  独立执行的管理员操作。Jetson 生命周期端口检查不属于此次选定的三项修复。

## 验证

新增回归测试在修复前复现 CFUN 和执行器 EOF 问题，修复后通过。覆盖 CFUN 应答/
回读丢失、恢复失败、单次恢复授权、身份拒绝、setup/recover、取消、管理保护拒绝，
以及首条消息前或 running 后 EOF、正常终态、执行器不可用、外部/未知/多监听器
归属、IPv6 通配监听、已停单元不能声明归属、检查失败、Web 不健康和现有启停幂等性。

窄范围验证通过：Jetson 后端 79 项；Spark 后端 57 项中一项为已有 macOS Unix
peer-credential 跳过；生命周期 42 项。本轮新增 17 个测试方法。
`make ci VENV=local/bootstrap-check` 也通过：Jetson 79 项、Spark 57 项（跳过一项）、
共享协议栈 156 项，合计 **291 项通过、1 项跳过**。两套前端生产构建、TypeScript、
文档、发布边界、许可证和 Shell 审计均通过，保留已有前端 bundle 大小警告。
本地验证使用 Python 3.11.15 / Node 24.14.0，未运行目标 Python 3.10/3.12 和浏览器 E2E。

Spark 的一次只读查询确认 SSH 用户可以通过 `ss --cgroup` 获取已安装 Web 监听器
归属，没有新增提权权限。三台设备均未执行服务、模组或路由变更。设备上的应用与
生命周期脚本仍需经过发布/更新，才能生效。本轮未生成 ARM64 包或发布校验和，
未验证回滚，也未关闭路线图 Gate。
