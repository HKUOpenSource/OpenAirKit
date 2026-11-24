# Empty-Core Deployment And Verification

`render.py` replaces the incomplete handwritten Compose template. It renders
`compose.json`, per-NF JSON configurations accepted by Open5GS's YAML parser,
the container runtime, and a SHA256 manifest. It uses the exact ARM64 image IDs
from `artifacts.lock.json` with `pull_policy: never`; arbitrary image variables
and tags are not accepted. `ext-DN` uses the minimal connectivity derivative built
from `Dockerfile.connectivity` (which removes `iperf3` and exposes only a fixed
`/health` endpoint on TCP port `8080`, without host-published throughput servers).

The 12 services are MongoDB, NRF, AMF, SMF, UPF, AUSF, UDM, UDR, PCF, BSF,
NSSF and ext-DN. SBI uses direct NRF discovery; SCP is not needed in this configuration.
In the pinned Open5GS source, SMF requests an SM policy association from PCF,
and PCF registers a binding with BSF. These data-session dependencies are
required even though this deployment has no IMS service. PCF obtains policies
from the independent subscriber database; no inline SUPI policy is generated.
NSSF supplies SST=1 without SD. No EPC/IMS daemons, sample subscribers or sample
SUCI private keys are loaded.

```sh
python3 stacks/open5gs/compose/render.py --output /tmp/aoc-v2-corecheck-01 --project aoc-v2-corecheck-01
python3 stacks/open5gs/compose/verify_bundle.py --bundle /tmp/aoc-v2-corecheck-01 --output /tmp/aoc-v2-evidence-01
```

Run the verifier on an ARM64 Docker host with the locked images loaded. It checks
file/image hashes, existing project/volume ownership, all host IPv4 routes and
Docker IPAM before running Compose. It refuses an existing evidence directory.
The test uses an internal bridge, no host-published ports and no gNB/UE. UPF TUN
and address changes occur only in its container network namespace.

Each NF receives its own fixed address and read-only config. Health requires the
exact daemon executable and expected bound sockets; AMF/SMF/UPF also require
working metrics. The verifier additionally checks NRF registrations and SMF/UPF
PFCP association. Healthy sockets are not session or radio evidence.

The test checks bounded stop, clean exits and MongoDB persistence across Compose
down/recreation. It then deletes only the disposable project and its newly
created, owner-labelled test volume. Normal deployment must retain the database
volume. Any unexpected container exit or forced termination is treated as a
verification failure and logged.

The default bundle is `production_ready: false` and is only for empty-core
validation. `--database-auth` generates private MongoDB credentials on the
deployment host; `--n6` enables namespace-local nftables NAT using the separately
locked UPF image. The verifier still refuses real provisioning project names and
deletes only disposable test volumes. It must never be run against a real SIM DB.

For one-time provisioning, render a fresh `aoc-v2-open5gs` bundle with
`--database-auth` on Spark, then use `../provision.py` with private material and
identity files. It starts only MongoDB and leaves its volume retained and stopped.
It refuses an existing volume; later deployment must reuse the same credentials
and volume, not regenerate a new bundle/password over it. Keys never go in command
arguments, output or Git. Duplicate subscriber insertion is refused without SQN
changes. Live radio installation and end-to-end PDU verification are covered in
the [Spark stack deployment guide](../../../deploy/spark/stack/README.md).

N6 tests bind source `10.0.0.1` inside UPF. They verify NAT and ext-DN traffic only;
they do not traverse GTP-U, an RAN, a Jetson or a real UE session.
