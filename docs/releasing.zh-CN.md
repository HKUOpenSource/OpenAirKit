# 发布指南

Jetson Console 与 Spark Platform 使用独立版本和发布包，一次只发布一个平台。

## 构建前

1. 同步更新后端 `__version__`、前端 package 文件、`CHANGELOG.md` 和
   `RELEASE-VERSION` 来源。
2. 核验 Python 锁、npm lockfile、上游源码版本和镜像摘要。
3. 运行 `make check` 以及对应前端 production build。
4. 运行 `make docs-audit`、`make release-audit`、`make license-audit`。

## 构建

先执行开发环境初始化。构建主机可使用 macOS 或 Linux、Python 3.10–3.12 和
Node.js 22；输出目录必须尚不存在。构建器会构建所选前端，并下载精确锁定的 Linux
ARM64 wheel：Jetson 对应 CPython 3.10 / Ubuntu 22.04，Spark 对应 CPython 3.12 /
Ubuntu 24.04。依赖条件按目标环境解析，因此在较新 Python 上构建 Jetson 包时也会
包含 `exceptiongroup`。

```sh
make build-jetson-release RELEASE_OUT=/tmp/agentic-ocudu-jetson
make build-spark-release RELEASE_OUT=/tmp/agentic-ocudu-spark
```

产物命名为 `agentic-ocudu-jetson-<version>-linux-arm64.tar.gz` 和
`agentic-ocudu-spark-<version>-linux-arm64.tar.gz`。每个包只能包含自身应用、
部署工具、锁定依赖、wheelhouse、版本、清单和第三方许可材料。

输出目录包含 `stage/`、压缩包及对应 `.tar.gz.sha256`；Jetson 还在暂存目录外保留
下载的 `wheels/`。清单记录源码提交、工作区改动状态、架构和 Python 目标。含未提交
改动的构建是开发候选包，不属于干净发布。归档前校验 wheel 标签、Python 要求、
依赖锁完整性与传递依赖。暂存只复制明确的应用/部署输入，排除另一平台和归档内容；
校验器拒绝校验和变化、额外文件和不安全路径。生成包不进入版本控制。

Shell 构建入口同样接受 `--output <新目录>`，通过环境变量 `PYTHON` 指定开发解释器。
底层暂存脚本仅供实现使用，不生成压缩包。

## 部署与验证

传输后核验摘要，解压到新的暂存目录，并在 install 前执行包内 preflight 与 verify。
安装不得启用开机自启，也不得改变另一个应用或协议栈。启动后检查健康、登录、SSE
和平台关键流程。

在解压后的 Jetson 包内执行 `python3 deploy/manage.py verify` 和
`python3 deploy/manage.py preflight`；Spark 包内执行
`python3 install.py verify --path .` 和 `python3 install.py check-host --path .`。
设备侧检查使用各平台要求的 Python 版本。这些检查不能替代安装/回滚实机 Gate。

## 回滚依据

升级前记录当前发布、数据库 schema 和备份路径。先回滚上一版本并验证健康，再重新
安装候选版本。脱敏验收记录需包含日期、源提交、版本、manifest 摘要、目标架构、
命令、结果、回滚标识和未验证项。
