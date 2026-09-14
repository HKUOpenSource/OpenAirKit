# Spark Platform 运维

## 平台生命周期

监测应用由 `aoc-observe.service`、`aoc-monitor-web.service` 和
`aoc-control.service` 组成。停止平台不得改变无线栈和核心网服务。健康检查：

```sh
curl -fsS http://127.0.0.1:8877/api/v1/health
```

浏览器通过 SSH 隧道访问，监听地址保持为回环地址。

## 监测

平台展示主机、B210、gNB、N2、核心网功能、接口、设备、会话和事件。数值必须带
来源时间与证据质量；SSE 中断后实时值变为 stale 或 unknown。N3、N6 与 bridge
计数器分别展示；能读取计数器不代表近期有流量，也不代表端到端路径已经验收。

Devices 页面只有在存在明确证据时才合并身份。无法确定时，RNTI 上下文与订阅会话
保持分离。Operations 页面在刷新后仍能展示任务步骤、失败、清理和审计记录。

## 协议栈生命周期

使用 `aoc-v2ctl preflight`、`prepare`、`start`、`status` 和 `stop` 管理本项目的
OCUDU/Open5GS 栈。启动要求核心网就绪、B210 无冲突、gNB 进程稳定且 N2 建立。
停止遇到异常容器或服务退出时会保留诊断所需资源并记录原因。

射频修改必须一次只变更一个变量，保存备份，并在相同条件下重新执行 UE benchmark
和 Spark evidence report。

## 升级与回滚

监测平台可在协议栈运行时升级。只停止三个平台单元，校验并安装发布，再启动并检查
健康与 SSE。回滚必须恢复上一发布和数据库备份，不能改变无线栈或核心网服务。
