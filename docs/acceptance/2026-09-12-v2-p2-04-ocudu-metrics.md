# V2 P2-04 OCUDU 指标适配验收记录

日期：2026-09-12
任务：V2-P2-04
固定 OCUDU 源码：`050a2bb`

## 实现

- `SchedulerFeed` 只连接 `ws://127.0.0.1:8001`，发送固定 `metrics_subscribe`，不接受浏览器参数或代理原始端点。
- 按 gNB InvocationID 分代；服务重启立即丢弃旧 sample，断流保持 unavailable，不输出假零。
- 小区/UE 指标包括 PCI、RNTI、DU UE ID、DL/UL bitrate、MCS、CQI、PUSCH SINR/RSRP、PHR、rank、DL/UL BLER、HARQ ACK/NACK 与 RRC 窗口计数。
- 不存在或固件未报告的字段输出 unavailable/scheduler_field_absent。BLER 没有 transport block 时不输出 0。
- underflow、overflow、late 使用有界增量日志 reader，按 inode/InvocationID 分代；首次打开跳过历史内容，超限和轮转不重放旧事件。
- 页面增加 MCS、CQI、BLER、SINR、HARQ 和射频异常趋势；无线配置继续来自 allowlist 字段。

## 实机字段核对

2026-09-12 只读 journal 样本包含 PCI/RNTI、CQI、RI、DL/UL MCS、bitrate、ok/nok、BLER、PUSCH、RSRP、BSR、TA 和 PHR，和适配字段一致。当前生产 gNB 的回环 WebSocket 端口拒绝连接，因为第一阶段最终配置保持 remote control disabled；P2-10 启用受限回环遥测并安装平台后，P2-11 必须以真实 JSON sample 再验收。

OCUDU 官方 receiver 示例同样发送固定 `metrics_subscribe` 并忽略带 `cmd` 的控制回复：<https://gitlab.com/ocudu/ocudu_docs/-/blob/20be4377c8646514a1644942ff81c6a3115845ce/docs/user_manual/outputs/assets/metrics_ws_receiver.py>。

## 自动验证

监测后端 25 项测试通过，覆盖字段单位、缺失字段、无 transport block、HARQ、聚合、进程分代和增量射频事件；React + TypeScript production build 通过。
