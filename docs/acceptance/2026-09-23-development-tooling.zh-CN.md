# 开发工具修复记录 — 2026-09-23

[English](2026-09-23-development-tooling.md) ·
[审阅基线](2026-09-23-development-readiness.zh-CN.md)

## 问题、调用路径与影响

问题：文档中的开发、测试和发布入口是否实际完成了其承诺的工作？当前检出没有
CodeGraph 索引。

- `make install-dev -> venv/pip -> npm ci/build`：创建所选隔离环境，检查
  Python 3.10–3.12，安装工具和两个应用的开发依赖，准备两个前端。保留已有环境，
  必要时通过 `VENV` 选择新目录。
- `make check / CI -> test-stack -> tests/`：Open5GS、资源预检、无线与发布工具
  的有效测试加入应用测试之外的默认覆盖。退役 SQL/IMS 部署和已移除的一次性修复
  测试迁至 `archive/development-baseline-tests/`，没有恢复废弃导入。
- `make e2e-spark -> scripts/e2e_spark.py -> Spark API -> Playwright`：创建临时
  鉴权、数据库和模拟观测值，使用继承的回环 socket 运行全部三组浏览器测试。
  执行器 socket 指向临时目录，失败会传播，结束时清理服务器进程，不能调用现网
  协议栈 helper。
- `make build-*-release -> scripts/build_release.py -> stage/download/verify
  -> archive`：构建 UI，按 Linux ARM64 CPython 3.10 或 3.12 选择 wheel，按
  目标环境解析依赖条件；检查锁完整性、wheel 元数据/标签、Python 与传递依赖兼容性。
  压缩包包含版本和源码元数据，另生成 SHA-256 文件。Spark 校验覆盖 wheel 摘要，
  安装器在修改主机前拒绝不符合要求的环境。

应用 API、模组操作和无线/核心网控制行为未变。本轮影响开发初始化、CI 和发布构建，
不代表完成安装或无线验收 Gate。

## 验证

- 新建 Python 3.11 环境成功安装后端依赖及两套 npm 锁定依赖，两个前端生产构建通过。
- `make check VENV=local/bootstrap-check`：Jetson 36 项通过；Spark 发现 51 项，
  跳过 1 项 macOS socket 测试；根目录 116 项通过；TypeScript 及文档、发布、许可、
  Shell 审计通过。
- 8 项发布工具回归测试覆盖目标条件解析、下载目标参数、正确与错误 wheel 标签、
  内部元数据不符、依赖缺失/损坏、依赖与 Python 要求，以及压缩包摘要/覆盖/符号链接
  拒绝。Spark 另有错误主机拒绝和 wheel 篡改测试。
- Spark 三组 Playwright 桌面/移动测试实际通过，覆盖导航、详情路由、登录过期/
  登出、证据过期、图表和响应式布局。这是模拟浏览器证据，不是射频证据。
- 两个真实离线包均已使用 ARM64 wheel 构建成功。工作区未提交，清单因此明确记录
  `dirty=true`。

获得用户明确授权后，仅向两台设备新建的临时目录传输了源码和锁定 wheel，
原生离线依赖安装和 `pip check` 均通过：

| 设备 | 原生 Python | 应用测试 | 根目录测试 | 测试后现网健康 |
| --- | --- | --- | --- | --- |
| Jetson | 3.10.12 | 36 项通过 | 116 项通过 | Web、device 均 `ok` |
| Spark | 3.12.3 | 51 项全部通过，无跳过 | 116 项通过 | collector 为 `ok` |

这些运行复现了 CI 矩阵中的平台后端和根目录测试，未触发 GitHub Actions 本身。
macOS 跳过的 socket 测试已在 Spark 通过。临时环境仅通过 `pip --no-index` 使用
已准备的 wheelhouse，没有安装系统软件包或调用现网生命周期操作。

两个压缩包均解压到新建本地目录，并通过包内校验器。压缩包 SHA-256：

| 产物 | SHA-256 |
| --- | --- |
| Jetson 0.3.0，发布 `619eb3735e7dfd91`，14 个 wheel | `6dacb782dfb4c6ca7d7d95087d0e6f0e74f2adf9f790b7d261f993b607341fb6` |
| Spark 0.1.0，发布 `d987aca4396311d2`，13 个 wheel | `da58c7c8414e9b44aca24d45e6ea280fd95e69915b4bbe5cbda91cf516fe4a3d` |

R06、P3-15/16/17 和 P3-GATE 保持未完成。没有修改现网包、服务、数据库、模组或
路由；实际安装/回滚/重装和无线故障注入仍需单独验收。
