# 受限维护权限

root 持有的 `/usr/local/sbin/aoc-maintain` 仅允许对应设备角色的固定操作。
首次安装需要管理员在设备终端输入密码，不保存密码，也不将密码发送给应用或代理。
初始化只配置访问权限，不安装应用、不重启服务、不修改模组，也不开启开机自启。

初始化程序对私有归档副本校验外部提供的 SHA-256，拒绝链接、路径穿越和未列入清单的
文件，通过 `visudo` 语法检查后将批准的内容复制到 `/opt/agentic-ocudu/maintenance`。
包、维护脚本、配置及状态均由 root 控制。sudoers 使用 `NOPASSWD: NOSETENV` 精确列举
每个动作，不授权通用 shell、Python、任意路径或通配符。每次操作校验内容哈希和权限，
使用固定子进程环境，并通过受保护的锁拒绝并发操作。

从已验证的应用发布目录构建：

```sh
python3 deploy/maintenance/build.py jetson --release /path/to/verified/stage --output /new/output
# Spark 使用 spark，额外纳入已审核的连通性升级脚本。
```

将 `bootstrap.py` 与 `approved.tar.gz` 放到设备私有目录。先以 SSH 用户验证包和生成的
sudoers，再安装。用独立记录的哈希和实际账户替换占位符：

```sh
python3 -I bootstrap.py --archive approved.tar.gz --sha256 DIGEST --user ACCOUNT --check
sudo /usr/bin/python3 -I bootstrap.py --archive approved.tar.gz --sha256 DIGEST --user ACCOUNT
sudo -n /usr/local/sbin/aoc-maintain verify
```

两端共有 `status`、`verify`、`install`、`rollback`、`start`、`stop`。
Jetson 另有 `ue-status`、`ue-maintenance`、`ue-resume`、`ue-recover`、`ue-job`，后者仅查询
本维护入口创建的恢复任务。Spark 另有 `radio-start`、`radio-stop`、`radio-restart`、
`core-start`、`core-stop`、`core-restart`、`connectivity-upgrade`。所有动作均不接受额外参数。
安装、回滚会影响本项目，可能中断数据连接，仍需按正常部署流程安排。Jetson 安装前会
停止平台；安装失败后检查状态，存在备份时使用保存的回滚检查点。Jetson 回滚仅使用本
入口安装时创建的检查点。没有既有鉴权配置的新安装会被拒绝。

本次批准覆盖当前包的精确内容；未来变更的发布代码需要管理员重新批准新包。哈希本身
不代表任意代码可信。既有管理权限保持原状；撤销本项授权时，由管理员删除
`/etc/sudoers.d/aoc-maintenance`。已有配置默认拒绝覆盖；管理员必须明确指定
`--replace-approval PREVIOUS_SHA256` 才能替换。替换时验证旧受保护包和已安装入口，
要求账户、角色及 sudoers 内容完全一致，持有维护锁并备份访问文件，激活失败时恢复。
非 root 的 `--check` 只校验新包和候选策略；旧状态由特权激活时检查。

本轮九项边界测试覆盖角色精确权限、非特权预检、哈希篡改、归档穿越与链接、额外代码、
错误所有者与权限、额外参数、固定子进程环境、明确批准包替换及激活失败恢复。
审阅问题是：如何在不存储密码的前提下
自动执行已审核的项目维护。调用路径为 `build -> bootstrap.unpack/check_policy ->
受保护安装 -> aoc-maintain.main -> approved -> execute`。两台设备均通过非 root
归档校验及各自原生 `visudo` 检查。管理员一次性启用后，两端均通过免密 `verify` 和
`status`，应用部署通过；Spark 回滚、重新安装和连通性升级也已通过。新版 Jetson
安装器在复用既有发布前验证包内文件、root 所有者和权限、运行路径及依赖。管理员批准的
更新已在两端启用；Jetson 前版本回滚、新发布安装及同一发布回滚后重装均通过实机验收。
系统 Wi-Fi 控制不在此授权范围内，仍使用正常管理员权限。

一次性 `repair-connectivity-manifest.py` 修复首版连通性升级器漏更新无线发布外层
清单的问题，需要管理员单独执行；现有入口不授权任意修复代码。脚本要求基站已停并
持有维护锁，核对 root 持有的原始备份、已审核代码与镜像及所有未修改文件。仅修改
外层清单的三个哈希，保留原清单并在写入失败时恢复，不操作服务、不扩大 sudo 权限。
更新后的升级器已将外层清单纳入正常校验和回滚，现已通过新的审核批准部署并完成
现网连通性升级，升级后核心网 12 个服务全部健康。

首次管理员执行在 `bin` 目录权限/所有者检查处退出，尚未写入。旧安装器会保留暂存
目录权限；修订后的修复要求发布根目录为私有 `0700`，逐个检查清单文件的父目录，
仅收紧该边界内 root:root 子目录的组写权限。链接、其他所有者/组及全局可写目录
仍会拒绝；普通文件仍执行原有严格权限与哈希检查。修复失败时恢复目录原权限，
成功时将权限变更记录保存在原清单备份旁。已在没有主机挂载的隔离 Linux 容器中用
真实 root 持有的 `0775` 目录验证，并通过可写程序拒绝及权限回滚测试。
