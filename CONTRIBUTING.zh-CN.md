# 贡献指南

[English](CONTRIBUTING.md)

## 工作流

修改应在 `feature/*`、`fix/*`、`release/*` 或 `hotfix/*` 分支完成，并使用
Conventional Commits。一次合并请求尽量只涉及一个应用或一项共享契约；说明
触发条件、最终行为、验证结果和回滚影响。

## 目录边界

- Jetson 应用修改放在 `apps/jetson-console` 和 `deploy/jetson`。
- Spark 应用修改放在 `apps/spark-platform` 和 `deploy/spark`。
- 协议栈修改放在 `stacks/ocudu` 或 `stacks/open5gs`。
- `packages/console-ui` 只能包含不带平台业务逻辑的共享 UI 原语。
- `archive/` 中的归档文件不得进入导入、构建或发布。

移动或删除模块时，应在同一变更中同步更新导入、测试、发布清单和文档，避免添加兼容封装层。

## 文档

运行时界面统一使用英文。架构、安装、运维、故障排查和发布文档必须提供
英文与简体中文配对文件。命令应能从文档注明的工作目录执行；仓库文件使用相对
链接；未实测的能力必须明确标记为未验证。

## 验证

开发过程中可按改动范围运行最小测试目标（`make docs-audit`、`make test-jetson-backend`、
`make test-spark-backend` 或 `make test-stack`），提交 Pull Request 前请运行 `make ci`。
`make ci` 会依次执行两端后端测试、协议栈与发布测试、两端前端 TypeScript 检查与生产构建，
以及全套仓库边界审计。

执行前请先运行 `make install-dev` 安装后端开发依赖（如使用自定义虚拟环境路径，请追加
`VENV=local/dev-venv`）；前端构建会自动执行 `npm ci`。自动 CI 对齐 Python 3.12 与
Node.js 22。若环境已准备完毕，也可以直接运行 `make check`。

- **自动 PR 门禁（`Quick checks`）**：在 Ubuntu 24.04 上对 Pull Request 自动执行 `make ci`。
- **手动扩展验证（`Extended checks`）**：通过 `workflow_dispatch` 手动触发，覆盖
  Jetson Python 3.10 / Spark Python 3.12 多版本矩阵及模拟服务浏览器 E2E 测试。修改前端交互
  或准备发布前建议运行该工作流；模拟 E2E 不操作真实硬件。

真实硬件验收摘要须严格脱敏后归档至 `docs/acceptance/`；发布打包规则见
[发布指南](docs/releasing.zh-CN.md)。

## 可选开发工具

当仓库根目录存在 `.codegraph/` 索引时，开发者可按 [CodeGraph 工作流](docs/coding-agent-codegraph.zh-CN.md)
快速定位符号与调用链。

严禁提交任何凭据、订阅身份、生产地址、数据库、原始日志、抓包、发布生成物或未脱敏截图。
