# ARM64 build and no-RF verification

This directory produces a **validation image**, not the production Compose release.
The image includes upstream test binaries and build dependencies. It does not start
EPC/IMS, copy subscribers, access USB, modify systemd, or publish host ports.

## Locked inputs

`../sources.lock.json` pins Open5GS v2.8.0, its required freeDiameter and Prometheus
C source archives, Ubuntu's ARM64 platform manifest, and MongoDB 8.0.30's ARM64
platform manifest. Linux uses packaged SCTP and libtins; Meson is invoked with
`--wrap-mode=nodownload` so missing dependencies cannot silently fetch branches.

The Ubuntu package resolver runs during the first image build. Exact installed
versions are captured in `/opt/aoc-evidence/packages.tsv`. Preserve the resulting
image ID and exported image archive for replay; rebuilding from APT at another
time is not promised to produce identical bytes. A production package must carry
that verified artifact or a separately verified build with a new evidence record.

## Prepare and build

Run from this repository on a Linux ARM64 Docker host. Preparation itself also
works on macOS, including metadata-free archive creation for transfer.

```sh
python3 stacks/open5gs/build/prepare.py \
  --output /tmp/aoc-open5gs-context \
  --cache /tmp/aoc-open5gs-sources \
  --archive /tmp/aoc-open5gs-context.tar.gz
docker build -t aoc-open5gs-validation:2.8.0-157f611 /tmp/aoc-open5gs-context
docker pull mongo@sha256:fa40191bb5b2d063bbdb6fb1d5f980a7c502f7355c11c6bc18812da2cb46ec6f
python3 stacks/open5gs/build/verify.py \
  --image aoc-open5gs-validation:2.8.0-157f611 \
  --output /tmp/aoc-open5gs-evidence
```

The build runs upstream `core`, `crypt` and `unit` suites. Verification starts
NRF/AMF/SMF in a disposable `--network none` container to check empty `/gnb-info`,
`/ue-info`, `/pdu-info` and Prometheus responses. A separate `--network none`
MongoDB uses tmpfs, validates its exact runtime version and a temporary read/write
operation, then shuts down. Both containers have CPU/memory limits, no host
mounts, no published ports, no USB/TUN devices and no Linux capabilities.

All created containers are uniquely named and tracked. A timeout, forced stop,
nonzero NF exit or failed cleanup prevents success. The checker removes only
its own containers and their anonymous volumes; it never removes image caches,
foreign containers, host bridges or shared databases. If the process is killed
before cleanup, locate its labelled resources before rerunning:

```sh
docker ps -a --filter label=org.agentic-ocudu.purpose=version-verification
```

Empty infoAPI responses validate availability and format only. They do not prove
registration, live device association, a data PDU, UPF forwarding, SQN recovery
or the final single-DNN configuration. Those remain subsequent acceptance work.

Open5GS and upstream dependencies retain their upstream licences in the staged
sources. The validation image is for local development; published artifacts must
include the corresponding source and applicable licence notices.
