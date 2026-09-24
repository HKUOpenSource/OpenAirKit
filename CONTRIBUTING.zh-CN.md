# 贡献指南

## 工作流

修改应在 `feature/*`、`fix/*`、`release/*` 或 `hotfix/*` 分支完成，并使用
Conventional Commits。一次合并请求尽量只涉及一个应用或一项共享契约；说明
触发条件、最终行为、验证结果和回滚影响。

## 目录边界

- Jetson 应用修改放在 `apps/jetson-console` 和 `deploy/jetson`。
- Spark 应用修改放在 `apps/spark-platform` 和 `deploy/spark`。
- 协议栈修改放在 `stacks/ocudu` 或 `stacks/open5gs`。
- `packages/console-ui` 只能包含不带平台业务逻辑的共享 UI 原语。
- 退役材料保存在当前源码树之外，不得进入导入、构建或发布。

不要为退役路径添加兼容导入。一次修改应同时更新导入、测试、发布清单和文档。

## 文档

运行时界面统一使用英文。当前架构、安装、运维、故障排查和发布文档必须提供
英文与简体中文配对文件。命令应能从文档注明的工作目录执行；仓库文件使用相对
链接；未实测的能力必须明确标记为未验证。

## 验证

开发时运行最小相关目标，提交评审前运行 `make ci`。它执行两端后端测试、一次
共享协议栈/发布测试、两端前端生产构建（含类型检查）和仓库审计。先安装后端
开发依赖，前端构建会自行运行 `npm ci`。使用 Python 3.12 和 Node.js 22 与自动
CI 对齐；已有 `make check` 仍可用于检查已准备好的开发环境。

每个 PR 只运行一个 Ubuntu 24.04 下的 `Quick checks` 作业。合并后不重复运行，
直接推送 main 不会自动检查；也可手动启动 `CI` 工作流。浏览器 E2E 和 Jetson
Python 3.10/Spark Python 3.12 矩阵移到手动的 `Extended checks` 工作流。
修改浏览器行为或发布前运行扩展检查，它使用模拟服务，不操作硬件。精简后的
自动 CI 不证明浏览器行为或 Jetson Python 3.10 兼容性；已知 E2E 时序问题仍会
在手动运行中暴露，本次调整不修复这些问题。

问题是每次修改需要哪些检查。仓库无 CodeGraph 索引，路径为
`pull_request → CI → make ci`，可选验证路径为
`workflow_dispatch → Extended checks → 后端测试 / e2e-*`。自动检查保留代码、
构建和仓库验证，移除浏览器启动、重复的共享测试及合并后的重跑。修改此约定时
验证工作流语法并运行 `make ci`。硬件验收仅在 `docs/acceptance/` 保存脱敏摘要，
发布验证见[发布指南](docs/releasing.zh-CN.md)。

不得提交凭据、订阅身份、生产地址、数据库、日志、抓包、发布生成物或未脱敏截图。
