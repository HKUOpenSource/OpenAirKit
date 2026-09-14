# 发布指南

Jetson Console 与 Spark Platform 使用独立版本和发布包，一次只发布一个平台。

## 构建前

1. 同步更新后端 `__version__`、前端 package 文件、`CHANGELOG.md` 和
   `RELEASE-VERSION` 来源。
2. 核验 Python 锁、npm lockfile、上游源码版本和镜像摘要。
3. 运行 `make check` 以及对应前端 production build。
4. 运行 `make docs-audit`、`make release-audit`、`make license-audit`。

## 构建

```sh
make build-jetson-release RELEASE_OUT=/tmp/agentic-ocudu-jetson
make build-spark-release RELEASE_OUT=/tmp/agentic-ocudu-spark
```

产物命名为 `agentic-ocudu-jetson-<version>-linux-arm64.tar.gz` 和
`agentic-ocudu-spark-<version>-linux-arm64.tar.gz`。每个包只能包含自身应用、
部署工具、锁定依赖、wheelhouse、版本、清单和第三方许可材料。

校验器应拒绝另一个应用、`archive/`、开发生成物、缓存、日志、诊断、生产配置、
符号链接和未锁定依赖。

## 部署与验证

传输后核验摘要，解压到新的暂存目录，并在 install 前执行包内 preflight 与 verify。
安装不得启用开机自启，也不得改变另一个应用或协议栈。启动后检查健康、登录、SSE
和平台关键流程。

## 回滚依据

升级前记录当前发布、数据库 schema 和备份路径。先回滚上一版本并验证健康，再重新
安装候选版本。脱敏验收记录需包含日期、源提交、版本、manifest 摘要、目标架构、
命令、结果、回滚标识和未验证项。
