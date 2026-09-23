# Astryx 真机部署 — 2026-09-23

[English](2026-09-23-astryx-deployment.md)

本记录对应 Astryx 初次部署。Jetson 后续已升级到
[0.5.1 实时更新修复版](2026-09-23-jetson-live-stream.zh-CN.md)。

状态：管理员激活精确维护授权后，已完成两台设备部署。两端均通过安装、回滚到
上一版本和重新安装验证，下表中的版本在本次部署时健康运行。未执行无线/核心网
重启或调制解调器恢复、复位操作。

| 平台 | 版本 | 本次部署发布 ID | 上一发布 ID |
| --- | --- | --- | --- |
| Spark | 0.2.0 | `5bc68497243efdf5` | `d987aca4396311d2` |
| Jetson | 0.5.0 | `c4e60f990fc61882` | `0826938fd08ae477` |

源码来自当前工作区，manifest 记录 `dirty=true`，包含 Astryx 迁移、Spark 完整
数字 Identity 及 Jetson P2 被动速率修复。后端、前端/锁文件、打包代码和变更记录
版本已同步。这些产物是开发候选包，不是来自干净提交的正式发布。

## 检查与暂存

- `make check VENV=local/bootstrap-check`：207 项通过，1 项平台相关跳过；两端
  类型检查及文档、发布、许可证、shell 审计通过。
- 两端 ARM64 离线归档构建通过，已验证 wheel 目标标签、锁文件集合和传递依赖。
- 两台设备均验证上传的归档 SHA-256、发布文件清单及授权包；管理员激活授权前，
  原生 `visudo` 策略检查已通过。
- Spark 主机检查通过。systemd-analyze 对一个无关 dashboard 单元提示权限不足，
  本次监控平台单元检查通过。
- Jetson 非中断预检通过。安装器停止旧 Web 服务后检查监听端口，安装和启动通过。
- 在独立的非特权检查环境验证原生依赖安装与模块导入，Spark 为 Python 3.12，
  Jetson 为 Python 3.10；发布包文件保持完整。
- 基线：Spark 三个监控单元、Jetson 两个 V2 单元均运行且未设开机启动。健康接口
  正常；Jetson 现有维护工具报告已注册、数据 PDU 激活、数据连通性已验证。

两台设备 SSH 用户家目录下的暂存目录分别为
`aoc-deploy/astryx-spark-0.2.0-20260923/` 和
`aoc-deploy/astryx-jetson-0.5.0-20260923/`，包含发布归档及校验文件、
`approved.tar.gz`、`bootstrap.py` 和 `approve.sh`。批准脚本先校验固定的归档与
bootstrap 摘要，只替换指定旧授权，再运行 verify；它不安装或重启应用。

## 授权边界

现有维护工具只允许对 root 拥有、哈希固定的已批准包执行精确操作，不能通过该
权限替换成新代码。参见[受限维护访问说明](../../deploy/maintenance/README.md)。
两台设备的普通 sudo 均需要密码，不通过聊天收集密码，也不将密码写入脚本。

| 平台 | 新授权包 SHA-256 |
| --- | --- |
| Spark | `0c15110a3b26cd0a1206db5d491bae39dcca58c88cd02d486ced3cbef2f2cf49` |
| Jetson | `f1c013f979ba20b1f4fe5f16dfc32fc2defb9ba2dc2b7d779e7065257185e705` |

管理员已激活两端暂存授权，部署前和完成后均验证了对应摘要。通过已有受限
`aoc-maintain` 操作逐台部署，先完成 Spark 部署与检查，再处理 Jetson。

## 真机结果与验证范围

- Spark：三个监控服务均运行，最终健康接口与采集器状态均为 `ok`。manifest
  中的 28 个文件哈希全部匹配。部署期间无线服务进程 ID 保持不变，12 个
  Open5GS 容器均健康。未新增开机启动设置。
- Jetson：两个 V2 服务均运行，未设开机启动，自动重启次数为零。Web 和设备健康
  均为 `ok`，manifest 中的 48 个文件哈希全部匹配。最新证据确认已注册、数据
  会话激活、绑定 RNDIS 的数据路径连通、实验策略匹配、管理链路受保护。
- 两端：HTTP 返回的 HTML 和两个入口 JS/CSS 资源均与安装文件一致；SPA 路由
  返回应用，未登录访问设备 API 返回 401。安装的前端目录均包含依赖许可证声明。
- 回滚：两端维护工具均成功恢复上一版本，已核对 current 链接且健康接口成功
  响应，随后重新安装批准版本并再次检查。Jetson 刚启动时设备证据短暂过期，
  最终新鲜采样已通过全部连接检查。
- 备份检查点由安装器管理：Spark 使用
  `/opt/agentic-ocudu/monitor/previous.json`，Jetson 使用
  `/var/lib/aoc-maintenance/jetson-rollback.json` 引用对应备份目录。
  实际回滚已验证这些检查点可用；未通过扩大管理员权限读取受保护的检查点内容
  或直接查询线上数据库 schema。
- Jetson 为 `maintenance=false`、`recovery_paused=true`：执行器现有关闭策略
  会在重启时持久化暂停标记。部署前自动故障恢复开启，部署后已暂停；普通连接
  验证正常。未通过恢复任务或调制解调器复位来修改这一状态。
- 没有可用的设备登录会话，因此未重新验证真机登录后的 UI/SSE。本地浏览器
  回归已在部署前通过；上述真机检查覆盖健康、安装资源、路由、未登录访问拦截
  和实时 UE 证据。这些开发构建仍记录 `dirty=true`。

问题：能否通过已有维护权限部署本次 UI 与 Identity 变更？仓库无 CodeGraph
索引。本次检查调用路径为 `build_release → maintenance.build → bootstrap
--check/replace-approval → aoc-maintain approved/execute → 平台安装器`。
影响为替换已批准的应用包，设备角色、用户及精确 sudo 操作清单保持不变。

## Manifest SHA-256

- Spark: `d37822fdad93c2c5fe842411b32b2de348fefd7d218d3e8f4e01afcf83634a9e`
- Jetson: `75b3e589053d14429347a093e081c881f908b5bc63ae9b86408d905f993097eb`

基础源码：`fd3b3b059b3e239912773d2c771c8fb5f64c5975` (`dirty=true`).
