# Jetson Console 运维

## 服务生命周期

日常在设备本地执行独立部署的快捷脚本：

```sh
~/aoc-ops/jetson/start.sh
~/aoc-ops/jetson/stop.sh
/usr/bin/python3 -I ~/aoc-ops/jetson/platformctl.py status
```

使用已完成 commissioning 的 SSH 用户执行。脚本使用系统 Python 和既有
`sudo -n /usr/local/sbin/aoc-maintain` 权限，不交互询问密码。启动并检查两个 V2 服务，
另行显示注册、PDU、数据连接、维护模式和恢复暂停状态。UE 未连接时显示警告，不自动
重连；不会请求接管、退出维护或模组恢复。执行器现有停止与恢复策略继续生效，停止
执行器可能持久化恢复暂停状态。

重复启动只检查已运行服务，不重启；重复停止确认两个服务、设备 socket 和网页监听均已
停止。启动要求设备已完成 commissioning，脚本不初始化新安装。失败时保留现场并停止
后续步骤。每次 helper 调用最多 330 秒，每次健康等待最多 60 秒。超时或中断后 systemd
任务可能仍在运行，重试前应先查询状态。

同一用户的各份脚本共用操作锁。不要同时通过网页或其他入口执行生命周期操作；此锁不
替代维护工具自身的权限及互斥检查。退出码：成功 0、执行或验证失败 1、参数错误 2、
脚本忙 3。`status` 成功读取状态即返回 0，服务停止不算查询失败。运行输出使用英文。

从设备上的仓库安装时，先备份已有目标目录，再复制三个独立脚本：

```sh
mkdir -p ~/aoc-ops/jetson
install -m 0755 deploy/jetson/start.sh deploy/jetson/stop.sh \
  deploy/jetson/platformctl.py ~/aoc-ops/jetson/
```

执行前核对传输哈希，也可通过 SSH 复制这些文件，设备不需要完整仓库。脚本从应用发布包
排除，不开启开机自启；撤回时恢复备份脚本，不回滚应用。脚本中不要加入站点地址。
实机结果见 [2026-09-24 启停验收](acceptance/2026-09-24-platform-lifecycle.zh-CN.md)。

管理员仍可使用底层已安装管理器：

```sh
sudo /opt/agentic-ocudu/jetson/current/venv/bin/python -I \
  /opt/agentic-ocudu/jetson/current/deploy/manage.py status
sudo /opt/agentic-ocudu/jetson/current/venv/bin/python -I \
  /opt/agentic-ocudu/jetson/current/deploy/manage.py start
sudo /opt/agentic-ocudu/jetson/current/venv/bin/python -I \
  /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
```

`stop` 必须在超时内终止 Web、设备执行器、受限 helper 和自有子任务。其他进程
打开模组前，应确认两个 systemd 单元都处于 inactive。

## 设备状态与配置

Overview 分别展示 SIM、驻留、5GS 注册、PDU 激活、地址池、RNDIS 地址和真实
数据路径。Device Setup 在写入前展示变更，并保存私有基线。重复 DNN、CID 冲突
或设备身份不确定都会停止流程。

维护模式会等待当前命令结束，暂停采集和恢复，并释放串口。退出维护后重新发现
设备并读取现场状态，不重放中断命令。

## 恢复与连通性

恢复任务先检查状态，只修复本项目拥有的路由；必要时每个任务最多执行一次模组
重连，并持久化步骤、取消和清理结果。命令超时后必须先回读，再决定是否继续。

网络中断后自动恢复先等待 120 秒，再最多尝试两次，间隔至少 300 秒。仅在用户
成功执行配置或恢复后启用；维护模式、管理保护不确定或次数耗尽会停止写入。
单个诊断目标不可达不会触发模组重置。数据验证持续健康达到冷却期后才重置尝试预算。

界面仅保留 Overview、Device Setup、History、Settings 四页。保留被动收发计数和
绑定接口的小流量探测，移除主动测速。独立状态含义见[UE 接入策略](ue-access-policy.zh-CN.md)。

## 升级与回滚

先停止平台并校验新发布，再安装、启动和验证健康，之后才能运行设备操作。回滚应
同时恢复上一发布链接和兼容数据库备份。如果任务修改过模组或网络状态，还需执行
记录中的设备恢复动作；只回滚应用代码不能恢复设备现场。

安装时将配置从 schema 2 一次性迁移到 schema 3，迁移前备份配置与数据库。
数据库 schema 2 保留旧测速历史，未结束的测速任务标记为中断与退役，不能再次执行。
回滚使用对应的升级前备份。
