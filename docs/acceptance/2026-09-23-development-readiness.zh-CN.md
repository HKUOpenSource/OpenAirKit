# 开发准备审阅 — 2026-09-23

审阅源码：`main` 分支的 `3ae3d76`，开始时工作区干净。
本文是带日期的审阅记录，不是新增任务清单或实机验收 Gate；任务状态仍以
[路线图](../roadmap.md)为准。[English](2026-09-23-development-readiness.md)

后续进展：[开发工具修复记录](2026-09-23-development-tooling.zh-CN.md)。

## 范围与方法

审阅问题：当前仓库和已部署系统能否支持下一轮开发，部署前必须补齐哪些检查？

核对了架构、路线图、CI、测试与构建入口、发布脚本和部分应用入口。当前检出没有
`.codegraph/` 索引，因此直接阅读源码。设备检查仅通过 SSH 读取 systemd 属性、
USB 清单、发布元数据和公开的本机健康接口。没有修改远端服务、无线、模组、路由、
订阅或配置。本文不保存私有地址、凭据、身份或原始运行日志。

## 实测设备基线

| 项目 | Spark | Jetson |
| --- | --- | --- |
| 系统 / 架构 | Ubuntu 24.04.4 / aarch64 | Ubuntu 22.04.5 / aarch64 |
| Python | 3.12.3 | 3.10.12 |
| 根分区可用空间 | 约 2.9 TB | 约 193 GB |
| 已识别硬件 | USRP B210 | Quectel RM520N-GL |
| 应用服务 | 三个平台服务 active | 两个 V2 服务 active |
| 健康接口 | `status=ok`、`collector=ok` | `status=ok`、`web=ok`、`device=ok` |
| 监听 | 回环端口 8877 | 回环端口 8878 |
| 开机策略 | 平台服务 disabled | V2 服务 disabled |
| 已部署发布标识 | `1fa5d5d7e6fd150d` | `cf2988ba2827ab78` |

Spark 无线服务 active，12 个本项目核心网/数据网容器报告 healthy。同时运行其他
工作负载，后续性能对照需考虑资源隔离。Jetson 的旧 `aoc-jetson-agent.service`
和 `aoc-jetson-web.service` 残留为 failed、disabled；V2 服务结果为 success，
重启计数为零。旧服务状态不代表 V2 故障。

两个现网发布包都没有当前构建器会生成的 `RELEASE-VERSION`。Jetson 清单记录
基准提交 `88a4b4d`、`dirty=true`；Spark 清单不记录源码提交。因此不能把现网
状态作为当前 `main` 的部署验收依据。健康接口和 USB 发现也不能证明当前 UE
注册、PDU、N2 或双向用户面正常。本轮未执行登录后 UI 验证、新鲜 UE 探测或测速。

## 问题与影响路径

1. **P1：默认检查通过不覆盖协议栈回归。** `Makefile:check` 和 CI 仅运行两个
   应用的测试，遗漏根目录 `tests/`。单独运行发现 116 项测试，1 项失败、12 项
   错误。其中 10 项错误和该失败来自 `tests/test_deployment.py ->
   scripts/aoclib/core.py` 中陈旧的 IMS 假设；另一个错误来自
   `tests/test_handoff.py` 导入已移走的辅助脚本。剩余一个错误属于环境问题：
   当前解释器缺少 `sqlparse`。应区分仍受支持的协议栈测试和历史测试，将退役内容
   归档，并把有效覆盖纳入 CI，不能为了旧测试恢复废弃导入或引入 IMS。

2. **P1：文档所述 ARM64 发布流程尚未闭环。**
   `Makefile:build-spark-release -> deploy/spark/platform/build-release.sh ->
   scripts/monitor_release.py:stage/download` 按构建主机的平台与解释器下载 wheel，
   没有指定目标，也没有 ARM64/Python 3.12 主机检查。在当前 Mac 上构建可能得到
   不适合设备的离线依赖。两个平台构建器都只生成目录，没有生成发布指南承诺的
   `.tar.gz`；Jetson 还依赖另行准备 wheelhouse。R06 前应明确并强制构建环境、
   验证 wheel 兼容性，并产出文档约定的压缩包。

3. **P2：Spark E2E 可在没有测试时成功退出。** `Makefile:e2e-spark` 指向不存在的
   `scripts/e2e/spark.sh`，只输出预览提示并返回成功。现有
   `apps/spark-platform/frontend/tests/browser.mjs` 没有接入此入口。应接入明确的
   模拟器/预览环境，并将缺少前置条件与测试成功区分。

4. **P2：文档开发初始化不足。** `make install-dev` 只安装
   `requirements-tools.txt` 中的 `sqlparse`，没有安装应用开发依赖或 npm 依赖。
   新环境仅按 README 两条命令不能可靠完成 `make check`。当前根目录 `.venv`
   使用 Python 3.9.6，缺少 FastAPI。应明确支持的 Python 版本、隔离环境以及
   前后端完整安装步骤。

## 验证结果与限制

| 检查 | 结果 |
| --- | --- |
| `make check PYTHON=.venv/bin/python` | Jetson API 测试导入 FastAPI 失败 |
| `make check PYTHON=local/monitor-venv/bin/python` | 通过；Jetson 36 项，Spark 发现 49 项、跳过 1 项 |
| 两个前端的 `npm run build` | 使用已有 node_modules 构建通过 |
| TypeScript、文档、发布、许可证与 Shell 审计 | 通过 |
| 现有 monitor 环境运行根目录 `unittest discover -s tests` | 116 项，1 项失败、12 项错误 |
| `make e2e-spark` | 未运行浏览器即返回 0，不属于 E2E 通过 |

备用 monitor 环境也是 Python 3.9.6，不能代替 CI 的 Python 3.10/3.12 矩阵。
Spark 跳过项是 macOS 禁用的 Unix socket 控制服务测试。本轮未执行从零依赖安装、
目标 ARM64 包安装、回滚或浏览器 E2E；静态审计通过不能证明这些环节已完成。

## 建议开发顺序

1. 修复开发初始化、有效协议栈测试覆盖和 E2E 入口，在 Python 3.10/3.12 重现基线。
2. 补齐发布流程，记录源码提交、架构、Python 版本和产物校验和；确认前版本可恢复后，
   按平台分别完成 R06、P3-16。
3. 完成 P3-15：先补模拟器，再采集串口竞争、接口改名、注册/PDU 分裂、残留地址、
   任务取消及登录过期的实机证据。相关运行边界为
   `api -> Agent.dispatch/execute -> Modem/Network -> Store`，模组访问继续统一
   由已有执行器管理。
4. 完成 P3-17：执行五次有界停止/启动与新鲜数据重连，每轮检查唯一模组控制者和
   管理连接。只有补齐新鲜注册、PDU、RAN、绑定接口的双向用户面、恢复和测速证据，
   才关闭 P3-GATE。

本次仅新增审阅文档，没有勾选路线图任务，也没有修改应用或部署行为。
