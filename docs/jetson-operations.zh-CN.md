# Jetson Console 运维

## 服务生命周期

所有生命周期操作都使用已安装的管理器：

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

## 恢复与测速

恢复任务先检查状态，只修复本项目拥有的路由；必要时每个任务最多执行一次模组
重连，并持久化步骤、取消和清理结果。命令超时后必须先回读，再决定是否继续。

测速强制绑定发现到的模组接口并核验实际路由。上下行必须来自同一任务；部分失败
单独保留，不能跨任务拼接。无法证明路由归属时，Wi-Fi 继续作为受保护管理路径。

## 升级与回滚

先停止平台并校验新发布，再安装、启动和验证健康，之后才能运行设备操作。回滚应
同时恢复上一发布链接和兼容数据库备份。如果任务修改过模组或网络状态，还需执行
记录中的设备恢复动作；只回滚应用代码不能恢复设备现场。
