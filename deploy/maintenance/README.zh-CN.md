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
不代表任意代码可信。撤销授权时，管理员可直接删除 `/etc/sudoers.d/aoc-maintenance`，不影响原有
系统管理权限。已有配置默认拒绝覆盖；更新批准包时须显式指定
`--replace-approval PREVIOUS_SHA256`。替换流程会核验既有受保护载荷、入口、
账户及角色一致性，持有维护锁并备份旧访问文件，激活失败时自动回滚。系统
Wi-Fi 控制不在本白名单授权范围内，仍使用常规管理员权限。
