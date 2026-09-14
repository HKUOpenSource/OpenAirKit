# V2 无线实时调度策略修复记录

日期：2026-09-11，更新于 2026-09-12。状态：现场修复、性能基线和后续天线配置试验均已完成；正式配置保持 1T1R。

## 触发证据

正式脱敏报告 `aoc-v2-evidence-report-05.json`（SHA256：`c4b0e9c1bb1c89cee71641086d34918b412bda771800fa244df4599f680b8c1e`）显示：V2 服务和 12 个核心网容器正常，但 gNB 日志窗口出现 `35,617` 次 RF underflow 与 `208` 次 late。该证据说明当前性能问题不能只归因于 UE 信号或核心网。

只读检查发现实际加载的 `/etc/systemd/system/aoc-v2-radio.service` 没有 `CPUAffinity` 和 `LimitRTPRIO`，`systemctl show` 返回空 CPU 亲和性和 `LimitRTPRIO=0`。源码安装模板随后补齐同样的限制，确保未来发布不会丢失该策略。

## 修复内容

同步到 Spark 的 `/home/defaultuser/aoc-v2-radio-realtime.py` 提供可回滚的 systemd drop-in：

```ini
[Service]
CPUAffinity=0-18
LimitRTPRIO=99
```

安装脚本只接受当前 V2 gNB unit，安装前保存原 drop-in，执行 daemon-reload，不自动启动服务；回滚通过输出的私有备份目录恢复。脚本 SHA256：`9117ff55ac1108e61d8bcf5ca4e18f7b18506a21be5b8fa0c616ce427b55e67f`。

## 现场复测门槛

用户在 Spark 执行安装并重启 `aoc-v2-radio.service` 后，必须确认 `systemctl show` 返回 `CPUAffinity=0-18`、`LimitRTPRIO=99`，再由 Jetson 重新注册并执行同参数 10 秒/1 流双向测试。随后重新生成脱敏 evidence report，比较 underflow/late 增量、信号指标、吞吐、TCP 重传和 N2 稳定性。只有复测通过，才重新勾选 P1-12、P1-13 和第一阶段 Gate。

当前没有修改 TX/RX 增益、TDD、频点、核心网、订阅或路由；物理天线、馈线和 UE 摆位仍需在现场确认。

## 高性能核心复测结果

第二版 drop-in 将 gNB 限定到 Spark 高性能核心 `5-9 15-18`，保留 CPU 19 给 B210 USB IRQ；Spark 实际生效配置为 `CPUAffinity=5-9 15-18`、`LimitRTPRIO=99`，gNB PID `2660322`。report-07（SHA256：`89f9b9c14ae69c690ff2981911be69a4990514bcdc470f98c0639acdc989ae12`）显示 lower-PHY TX/RX/UL 线程落在 CPU `16/17/9`，late 为 0，underflow 为 117，较 report-06 的 171 下降约 32%。

同次 Jetson 测试仍通过注册、PDU、地址池、绑定路由和双向用户面，但 RSRP `-111 dBm`、RSRQ `-10 dB`、SINR `4 dB`，上行 `2.907718 Mbps`、下行 `16.119725 Mbps`，TCP 重传为 0。由于信号条件相对上一轮明显变差，不能把本轮吞吐下降归因于 CPU 策略，也不能把 underflow 117 视为已闭环。下一步先固定天线/UE 摆位并重复同条件采样，再考虑单变量 RX/TX gain 测试。

## 信号改善及持续 underflow 诊断

2026-09-12 的同参数单次复测中，Jetson 为 RSRP `-104 dBm`、RSRQ `-10 dB`、SINR `16 dB`，上行 `5.735310 Mbps`、下行 `35.694879 Mbps`，TCP 重传为 0；注册、数据 PDU、地址池和绑定 RNDIS 的同次双向路径均通过。该结果证明物理摆位改善了本次信号和吞吐，尚不能证明实时错误已经消失。

report-09（SHA256：`ea48c63db9870e7dda0b83e8e33fdf704046223a7f4e56c0a740e12e96a17e08`）加入脱敏的分钟级异常聚合。相同 gNB invocation `9c422e05d1a0479cbbaa5d40e3d2b251` 自 2026-09-11 14:44 HKT 持续运行；报告累计 underflow `43,288`、late `111`，RLF、HARQ 重传耗尽、fatal 和会话失败均为 0。最近四小时每分钟均出现 underflow，通常约 12–54 次；测速所在 07:30 UTC 分钟为 27 次。因此 underflow 是持续的 RF 时序问题，并非由本次 iperf3 负载触发。

主机只读采样显示 B210 仍通过 5000 Mbps USB3，V2 gNB 使用高性能核心并保留 CPU 19 给 USB IRQ。同期非本项目 `dcvc-rt-demo` 视频容器的 `python -B app.py` 约占 1.6 个 CPU，工作线程覆盖 gNB 的 CPU 集合；Firefox 亦有持续负载。已准备固定目标、自动恢复的短时 A/B 工具，只比较该视频容器运行和暂停时的 RF 日志增量，不改 gNB、UHD、核心网或射频参数。完成 A/B 前不调整已经与 OCUDU B210 参考配置一致的 64 个收发 frame buffer。

短时暂停 A/B 已完成，输出 SHA256 为 `c40acb815dd003293e324f492a755d76cad51d54e6364ce11254fbaa2a7e2e95`。视频容器正常运行的 60 秒基线产生 underflow `52` 次；暂停后的 60 秒产生 underflow `0` 次，两个窗口的 RF late 和 lower-PHY late 都为 0。脚本随后确认视频容器已恢复运行且未处于 paused，gNB PID、invocation 和服务状态均未改变。该对照为同机视频负载导致 RF 时序抖动提供了直接证据；下一步测试把视频容器限制到 `0-4,10-14`，继续运行其业务并与 gNB 的 `5-9,15-18` 及 USB IRQ 的 CPU 19 分离，结束后恢复原空 CPU set。

第一次 CPU 集 A/B 的两个 60 秒采样已执行，但 Docker 将空 `cpuset` 更新解释为不改变现值，脚本在恢复校验处停止，未写出统计 JSON。随后将容器恢复为主机全部在线 CPU `0-19`；容器持续运行，gNB PID 和 invocation 均未改变。工具已修复为空配置使用 `/sys/devices/system/cpu/online` 的明确值，并通过专项及全部 V2 测试；该失败不计为 CPU 隔离效果证据，需缩短窗口重新采样。

修复后的 30 秒 CPU 集 A/B 输出 SHA256 为 `90c5999a34108de79846e76d0ed39eaaf21762701cad3a03aa4d70291523a273`。共享全部 CPU 的基线产生 underflow `53` 次；视频容器继续运行但限制到 `0-4,10-14` 后产生 underflow `0` 次，两个窗口的 late 和 lower-PHY late 均为 0。脚本确认视频容器恢复为 `0-19` 且 gNB 运行实例未变化。该结果证明 CPU 集隔离能够在不停止视频容器的情况下消除短窗口 RF underflow；仍需在隔离窗口执行真实 UE 测速，再决定是否固化运行策略。

CPU 集隔离下的真实 UE 测速通过，上行 `7.443454 Mbps`、下行 `36.594060 Mbps`，TCP 重传为 0，数据地址仍为 `10.0.0.8`，注册、PDU、地址池和绑定路由均保持正常。Spark 同窗报告 SHA256 为 `7dad3a149492cdf49a3449dab3492cb3c9d61d6af18a6c969763bded06cf207b`；60 秒内仍出现 underflow `53` 次，late 和 lower-PHY late 为 0，随后视频容器恢复 `0-19`，gNB 未重启。因此 CPU 集隔离改善了本次吞吐并消除了空闲窗口 underflow，但尚未消除承载业务时的 underflow。下一步在视频容器完全暂停的同参数测速窗口复测，以区分剩余的共享主机资源干扰和 gNB/UHD 数据路径本身。

## A/B 时间窗口修正及下一变量

复核发现 gNB 文件日志按 4 KiB 批量刷盘，前三份 A/B 输出的 `bytes` 都恰为 4096；文件偏移窗口中包含窗口开始前已经缓冲的事件，也可能缺少窗口结束前尚未刷盘的事件。因此这些文件的 underflow `0/52/53` 不能作为严格时间窗口证据，前述“空闲窗口归零”的结论撤回；UE 测速、容器恢复和 gNB 未重启证据不受影响。

改用日志内事件时间过滤并确认 `range_complete=true` 后，CPU 集隔离加 UE 测速的 60 秒窗口有 underflow `42` 次，报告 SHA256 为 `d5639509e39f4693d4c787d3b029d6bb38d5a22e9ba64ff4e02ce220503b6a66`；视频完全暂停加 UE 测速的 60 秒窗口有 underflow `20` 次，报告 SHA256 为 `4c557a422c0da7423e70006b603a5020a391a62867f294d86b5ac2ba17ba51b0`。两者 late、RLF、HARQ 重传耗尽、fatal 和会话失败均为 0。暂停窗口的 UE 上行 `7.372193 Mbps`、下行 `32.724825 Mbps`，TCP 重传为 0。

结论：同机视频负载会加重 RF 时序压力，但不是全部原因；完全暂停后业务窗口仍有约 `20` 次 underflow。下一项单变量为将 UHD `num_send_frames` 从 64 调到 128，保持 `num_recv_frames=64`、23.04 Msps、sc12、增益、TDD、CPU 策略、核心网和 UE 测试参数不变。试验工具会在无线服务完全停止后更新 V2 runtime 与完整性清单，保留可验证备份且不自行启动服务；未复测前不写入正式发布默认值。

## UHD 发送缓冲 128 帧首轮结果

可回滚试验已将运行实例设置为 `num_recv_frames=64`、`num_send_frames=128`，备份为 `/var/lib/agentic-ocudu/v2/radio-buffer-1789205561938244760`。report-10（SHA256：`9b48e8c6f00c91b9588f6c86fa34873aa75ee95bd658fd923e8614a7ec7d02a8`）确认实际运行配置、gNB 服务健康、12 个核心网容器健康、活动数据会话 `QFI=1/5QI=9`，并确认 gNB PID `2144509`、invocation `97f0a12efc72466e821ac8f5dab6e72d` 在测试期间未变化。

视频容器限制到 `0-4,10-14`、gNB 保持 `5-9,15-18`、USB IRQ 保持 CPU 19 的 60 秒业务窗口已完成。按日志内事件时间过滤的报告（SHA256：`575d2f3cf808d024041ba3eb8a9c6936bec3227eb1404116affabd2b096f54e1`）为 `range_complete=true`，记录 underflow `35/60s`、late `0`、RLF `0`、HARQ 重传耗尽 `0`、fatal `0`、会话失败 `0`。同窗 UE 测速上行 `7.307507 Mbps`、下行 `35.670994 Mbps`，TCP 重传为 0，注册、PDU、地址池和绑定路由均通过。

与同条件的 64 帧 CPU 集隔离窗口 `42/60s` 相比，首轮 underflow 下降 7 次，约 `16.7%`。单个窗口不足以排除自然波动，因此保持 128 帧运行配置并继续完成两次同条件复测，源码默认值未改变。

第二、三次时间戳范围报告均为 `range_complete=true`，underflow 分别为 `57/60s` 和 `45/60s`，SHA256 分别为 `fc2b7d7ad90435e13511f914c4efd0dea4186587f60f2a0ef576ce53335d543d`、`177333c695ddc3f5687e1cb75cbc7e9c3807c78ee73b263088fb5d0b126cb68e`；两个窗口的 late、RLF、HARQ 重传耗尽、fatal 和会话失败仍全部为 0。对应 UE 测速为上行 `7.793517/7.877981 Mbps`、下行 `34.871816/33.394526 Mbps`，TCP 重传均为 0。第三次连接前无线状态为 RSRP `-106 dBm`、RSRQ `-10 dB`、SINR `13 dB`。

三次 128 帧 underflow 为 `35/57/45`，中位数 `45/60s`、范围 `35–57/60s`；吞吐中位数为上行 `7.793517 Mbps`、下行 `34.871816 Mbps`。中位 underflow 没有优于 64 帧单窗基线 `42/60s`，因此不能证明发送缓冲加倍有效。试验判定为无效，运行配置应从备份 `radio-buffer-1789205561938244760` 恢复为 64/64；恢复和复验完成前 P1-12、P1-13 与第一阶段 Gate 继续保持未勾选。

## 外部负载停止及 CPU 排他对照

128 帧试验已从备份恢复。report-11（SHA256：`e76a2856d738d6eb37f4281677550335996bf87ca90945b1f6f26ff6704817c5`）确认运行配置回到 `num_recv_frames=64`、`num_send_frames=64`，gNB 和 12 个核心网容器健康；恢复后 UE 上行 `7.970193 Mbps`、下行 `35.906040 Mbps`，TCP 重传为 0。该结果确认 128 帧没有吞吐优势，源码默认值始终保持 64/64。

用户报告已停止 dcvc 服务后，只读核验发现 `dcvc-rt-demo` 容器仍在运行并占用约 `95.27%` CPU。按用户要求停止该外部容器；它在 20 秒优雅退出期限后为 exit 137，未删除、未修改重启策略，也不作为 V2 服务验收结果。gNB PID 和 invocation 在停止动作前后未变化。

在 dcvc 已停止、UHD 64/64 下进行了同参数对照。临时将 `user.slice` 和 12 个 V2 核心网容器移到 `0-4,10-14,19` 的排他窗口为 underflow `1/60s`，报告 SHA256 为 `b5e842a3cfbb5bdddbbab101ac88b85e409434da8b043d9970263f628589e633`；UE 上行 `7.760836 Mbps`、下行 `33.922927 Mbps`，无线状态 RSRP `-106 dBm`、RSRQ `-10 dB`、SINR `14 dB`，TCP 重传为 0。工具首版恢复时 `AllowedCPUs` 已清空但 `EffectiveCPUs` 未扩回全部核心；现场立即显式恢复为 `0-19`，随后修复工具按实际 `EffectiveCPUs` 校验，全部 V2 测试通过。

dcvc 同样保持停止、但不启用 CPU 排他的对照窗口为 underflow `0/60s`，报告 SHA256 为 `2f4cb4411a8195ce9427233eea862fe2dc5802c27cbfc92fff787eb0482bdb71`；UE 上行 `7.947792 Mbps`、下行 `34.991566 Mbps`，无线状态 RSRP `-105 dBm`、RSRQ `-10 dB`、SINR `14 dB`，TCP 重传为 0。两个窗口均无 late、RLF、HARQ 重传耗尽、fatal 或会话失败，gNB 实例保持不变。该对照不支持固化更复杂的 CPU 排他策略；主要改善来自移除同机高负载 dcvc 工作负载。

由于 gNB 文件以 4 KiB 批量刷盘且服务重启会轮转日志，证据工具已改为按事件时间查询最多 16 个严格命名的当前/轮转 gNB 日志，每文件最多读取末尾 16 MiB；仅输出文件名、时间边界和脱敏计数。跨轮转测试及全部 57 项 V2 测试通过。下一步在 dcvc 停止、无临时 CPU 排他、UHD 64/64 的当前条件下完成三次同参数性能基线，并对完整基准时间范围复核 RF 异常。

## 最终性能基线与第一阶段结论

在 dcvc 停止、无临时 CPU 排他、UHD 64/64、高性能核心亲和性保持 `5-9,15-18`、USB IRQ 保持 CPU 19 的条件下，Jetson 完成三次独立的 10 秒/1 流同任务双向测试。三次注册、数据 PDU、地址池、绑定 RNDIS 路由及双向用户面全部通过，模组未重置，IMS/SOS/厂商上下文在基准前后不变，TCP 重传全部为 0。

上行结果为 `7.959831/7.863492/7.830139 Mbps`，范围 `7.830139–7.959831 Mbps`、中位数 `7.863492 Mbps`；下行结果为 `37.970838/37.546842/37.781378 Mbps`，范围 `37.546842–37.970838 Mbps`、中位数 `37.781378 Mbps`。UE 固件不支持 `AT+C5GQOSRDP`，因此 UE 侧动态 QoS 保持 `unsupported`；该限制没有被转换成 false success。

最终跨轮转范围报告覆盖 `1789214186.7742136–1789214281.4730117`，`range_complete=true`，SHA256 为 `c55a576d77f1b85e2863f65d93f9df23ca7e2b29278f0a64c4399c7048a81624`。约 95 秒窗口内 underflow、late、RLF、HARQ 重传耗尽、fatal 和会话失败全部为 0。report-12（SHA256：`a4b0650552dc0b0bccbc9343c1d33013ca6815f6d919e3491cdebec88b287a70`）无采集错误，确认重启后的 gNB active/running、12 个核心网容器 healthy、运行配置 64/64、活动 `oai` 数据会话地址池有效以及核心网侧 `QFI=1/5QI=9`。

结论：report-05 暴露的持续 RF underflow/late 已在当前交付条件下闭环。保留高性能核心实时策略和 OCUDU B210 参考的 64/64 缓冲；不保留 128 帧或额外 CPU 排他试验。停止同机高负载 dcvc 工作负载是消除持续 underflow 的必要运行条件之一；V2 不接管或自动控制该外部容器。V2-P1-12、V2-P1-13 与第一阶段 Gate 通过，不增加固定时长观察门槛。

## 2T2R 候选评估与回滚

在第一阶段 Gate 通过后，又对 B210 进行了可回滚的 2T2R 候选评估。候选配置使用两个完整收发链路、`nof_antennas_dl=2`、`nof_antennas_ul=2`、每通道 TX gain `77`、RX gain `68`；运行时首先通过配置 dry-run，再由 stdout 调度指标确认下行 RI 约 `1.9–2.0`，证明 Rank 2 确实生效，并非只改了配置文本。

固定 64/64 UHD 缓冲时，两组三次基准的合并中位数约为上行 `6.80 Mbps`、下行 `39.67 Mbps`。相较正式 1T1R 基线，上行由 `7.86 Mbps` 降低约 `13.5%`，下行由 `37.78 Mbps` 提高约 `5.0%`。两个完整测速范围各出现 4 次 RF underflow，范围报告 SHA256 分别为 `e23e23ab7b21f389e3ad70abf4fb281ba913df12fcb7061d84a90ba4a55c046f` 和 `fa6fb09974f8f3781a8e47f7bd24bcfb1d0182b0fb2ecba9d62ec34fa1c9e217`；late、RLF、HARQ 重传耗尽、fatal 和会话失败均为 0。report-14（SHA256：`808f80dfd3983f4bfea787893437d9f14767c812fc2dfaa99f1de3f6169b520c`）确认当时 2T2R、核心网健康和活动 `QFI=1/5QI=9` 会话。

随后只把 2T2R 的发送缓冲从 64 增至 128，三次基准中位数为上行 `5.97 Mbps`、下行 `39.07 Mbps`，完整范围仍有 2 次 underflow（SHA256：`e39da142e887ab9f4146044ea279a2ffe936a1fb4c4ca85ce5fb5cc2e05a802e`）。report-15（SHA256：`3cb2d080b0ed25c9d90f22224b8c0cd70ceee2d66f1ddfe669c4805ba933c5b9`）确认该运行实例；该变量没有净收益，也已回滚。

因此 2T2R 候选被拒绝：它能建立 Rank 2，但当前 B210、20 MHz、小区调度、天线环境和 UE 组合下，下行提升有限，上行下降且出现可重复 underflow。回滚后的 report-17（SHA256：`f830b7f5344dcfc0de4f3ba23cfd786032d4e2f54436ef66dffc376ee878a6e0`）以及最终 report-19（SHA256：`b21991d970e64802f3919769fea2935f560fc28403e6d83e057e18ed70923a89`）均确认实际运行配置恢复为 1T1R、TX gain `80`、RX gain `68`、UHD 64/64；高性能核心亲和性 `5-9 15-18` 和 `LimitRTPRIO=99` 保持生效。最终 gNB active/running、`NRestarts=0`，12 个 Open5GS 容器 healthy，活动 `oai` 会话地址池及 `QFI=1/5QI=9` 均有效，采集错误为空。

## 链路预算与近距离性能验证

回滚后的首次 1T1R 三次基准一度降至上行中位数 `1.37 Mbps`、下行中位数 `30.01 Mbps`，其中一次下行有 53 次 TCP 重传。对应完整日志范围没有 underflow、late、RLF、HARQ 重传耗尽、fatal 或会话失败（SHA256：`cbd20b4acf8b06a5d0c7887d07918c415d8f39c62504eb264c6177706259b662`），report-18（SHA256：`4311ce70f65f70fa9f7f3aef238b38290b3639466493f1275ccb2cfba7ab2d99`）也确认配置和服务健康。因此该下降没有被归因于回滚或实时调度故障。

调度指标进一步显示，原摆位下 PUSCH SINR 约 `12–15 dB`、UL MCS `8–12`、PHR `-12/-13 dB`，UE 明显受上行功率预算限制。将 UE 移至 B210 附近的可控视距位置后，QENG 改善至 RSRP `-86 dBm`、RSRQ `-10 dB`、SINR `34 dB`；同参数测试达到上行 `11.551709 Mbps`、下行 `58.957542 Mbps`。同期 PUSCH SINR 约 `24 dB`、UL MCS `24–25`、PHR `+3/+4 dB`，下行 CQI `15`、MCS `27`，gNB 调度约 `64 Mbps`，DL BLER 为 0，且没有 RF underflow。

不限速下行的 TCP sender 出现 `766–871` 次重传，但 gNB DL BLER 仍为 0；独立复测的接收速率为上行 `11.578761 Mbps`、下行 `58.015565 Mbps`。将反向下行限制为 `50 Mbps` 后，接收速率为 `50.016595 Mbps` 且 TCP 重传为 0。这组对照说明不限速重传来自接近承载上限时的排队和拥塞，不能直接解释为无线 BLER。

当前正式运行结论保持 1T1R、TX gain `80`、RX gain `68`、UHD 64/64。性能对比必须固定 UE 与天线距离、方向、极化和周边遮挡；单纯提高 RX gain 没有证据支持。B210 当前使用 `TX/RX A` 作为唯一收发链；`RX2 A`、`RX2 B` 是各通道的可选接收端口，当前配置没有选用。2T2R 候选使用 `TX/RX A` 与 `TX/RX B`，试验已回滚。临时 stdout 指标已关闭，最终 report-19 对应正常交付状态。
