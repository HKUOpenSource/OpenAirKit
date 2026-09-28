# Spark stack deployment

[简体中文](README.zh-CN.md)

`runtime.py`, `package.py` and `systemd/` are the supported source for the independent
OCUDU/Open5GS lifecycle. They install separately from Spark Platform. The source
CLI is `python3 scripts/aocctl --help`; the installed CLI is `aoc-v2ctl`.
Retired templates and installers are archived and are not package inputs.

## Prepare a private candidate

Use Python 3.10–3.12. Build the pinned OCUDU binary using
`python3 stacks/ocudu/scripts/build.py --workspace /path/to/private-radio --jobs 2`
on the ARM64 build host. Keep its `build-result.json`. Compile the probe without
running it, using the reviewed UHD installation:

```sh
c++ -std=c++17 stacks/ocudu/scripts/probe_b210.cpp -o /path/to/private-radio/probe-b210 $(pkg-config --cflags --libs uhd)
```

Obtain Open5GS images from the pinned build inputs under `stacks/open5gs/`.
Generate the private authenticated N6 bundle with:

```sh
python3 stacks/open5gs/compose/render.py --database-auth --n6 --output /path/to/private-core
```

The supported site profile is the repository's default core subnet, single data
PDU and twelve services. Provision the owned MongoDB volume separately with
`stacks/open5gs/provision.py`, using private subscriber material and the same core
bundle. This operation requires an explicitly scheduled device phase. Do not copy
another platform's database. Staging below is offline and preserves the input
bundle, including its private credentials; it does not provision or start anything.

```sh
python3 deploy/spark/stack/package.py stage \
  --core /path/to/private-core \
  --binary /path/to/private-radio/build/apps/gnb/gnb \
  --probe /path/to/private-radio/probe-b210 \
  --build-record /path/to/private-radio/build-result.json \
  --output /path/to/new-private-stack-release
python3 deploy/spark/stack/package.py verify --source /path/to/new-private-stack-release
```

Staging checks ARM64 ELF headers, the gNB hash and pinned build revision, core
file hashes and service membership. It records every file, including the probe,
controller and both units. The output is a private deployment candidate containing
site configuration, not a shareable application archive. Never add it to Git.

## Install later, in a device maintenance window

This source change has local synthetic validation only. Target installation,
service validation and RF acceptance are separate, pending work.

Transfer the reviewed candidate privately and verify its independently recorded
checksum. From a trusted checkout, run `package.py verify --source CANDIDATE`, then
`sudo python3 deploy/spark/stack/package.py install --source CANDIDATE` on ARM64 Linux.
The installer checks pinned images, volume ownership, resource conflicts and unit
syntax. It copies into private root-owned storage, rechecks the copy and installs
`/opt/agentic-ocudu/v2`, two V2 units and `/usr/local/bin/aoc-v2ctl`.
It never starts/enables services, changes subscriber data or touches the monitor.
Existing installations, units or CLI paths are rejected; this is a fresh-install
path, not an in-place upgrade. A failed install removes only files it just created.

Use `preflight`, `start`, `status`, `stop` with the installed controller. `prepare`
opens the free B210 to verify its identity/gain limits, writes private configuration
and dry-runs the gNB. It requires a healthy core and normally runs as the radio
unit's callback. `start` orders core before radio through systemd dependencies and
requires both current SCTP and successful NG Setup from infoAPI. Failed startup
retains state for diagnosis. Stop checks radio exit before stopping core and never
removes the database volume. Do not mix CLI, Web and maintenance-helper operations.

Telemetry is disabled in the initial radio configuration. The separate
`scripts/spark/enable_radio_json_metrics.py` transaction installs the loopback
access guard and enables JSON metrics; schedule it with the monitor setup before
accepting collector telemetry. CPU placement remains a site-reviewed policy;
this package does not copy a particular host's CPU affinity.
