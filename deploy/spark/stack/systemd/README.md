# Stack service definitions

[简体中文](README.zh-CN.md)

The stack package installs `aoc-v2-core.service` and `aoc-v2-radio.service`.
Core is a oneshot service with retained active state; radio requires and binds to
core, runs the gNB with `LimitRTPRIO=99` as its main process and checks current
N2 setup after launch. Neither unit has an Install section or enables boot
startup. Site-reviewed supplementary units and drop-ins live alongside them:
`aoc-v2-cpu-latency.service` (`PartOf=aoc-v2-radio.service`, paired with
`aoc-v2-radio.service.d/cpu-latency.conf`) holds `/dev/cpu_dma_latency=0` while
radio runs, and `aoc-v2-radio.service.d/realtime.conf.example` provides a CPU
affinity template for hosts shared with other workloads. Monitor services are
packaged independently. See the [stack package guide](../README.md).

Installation verifies staged unit syntax with staged executable paths, then writes
the fixed installed paths. Local tests replace systemd/Docker commands with inert
functions; target systemd and RF behavior remain unverified by these tests.
