# End-to-End Quickstart

[简体中文](quickstart.zh-CN.md)

This guide walks you from bare hardware to a working end-to-end 5G SA system
managed by **Spark Platform** and **Jetson Console**. Each step lists the exact
pass criteria before moving on; links point to full reference details.

```mermaid
flowchart LR
  S0["0. Hardware & Prereqs"] --> S1["1. Spark 5G Stack & Platform"]
  S1 --> S2["2. Open5GS Subscriber & TB01 SIM"]
  S2 --> S3["3. Jetson Console & UE Bring-up"]
  S3 --> S4["4. End-to-End Check & Optional Boot"]
```

## Before You Start

1. Confirm all hardware, wiring and OS requirements in [Hardware, Topology and Prerequisites](hardware-and-topology.md).
2. On your development host, verify the repository toolchain and audits (optional if consuming pre-built releases):
   ```sh
   make install-dev BOOTSTRAP_PYTHON=python3.12
   make check
   ```
3. Prepare an off-repo, access-restricted directory (`chmod 0700`) for site-private SIM credentials, candidate bundles and backup records. Never commit secrets to Git.

---

## Step 1 — Deploy Spark 5G Stack & Spark Platform

On **DGX Spark** (or from your ARM64 build host):

1. **Build and install the OCUDU + Open5GS stack**:
   Follow [Spark stack deployment](../deploy/spark/stack/README.md) to build the pinned OCUDU `gnb` binary and `probe-b210`, render the private N6 Open5GS bundle (`stacks/open5gs/compose/render.py --database-auth --n6`), initialize MongoDB (`stacks/open5gs/provision.py`), and stage/verify/install via `deploy/spark/stack/package.py`.
2. **Build and install Spark Platform (`0.2.1`)**:
   Build the release archive with `make build-spark-release` (see [Releasing](releasing.md)), transfer it to Spark, and follow [Spark setup](setup-bs-spark.md) to run `install.py verify`, `check-host`, and `sudo python3 -I -B install.py install --path .`.
3. **Enable guarded OCUDU JSON metrics (`127.0.0.1:8879`)**:
   Run `scripts/spark/enable_radio_json_metrics.py` so telemetry runs on `127.0.0.1:8879` behind `aoc-v2-metrics-guard.service` (keeping `8000–8002` free).
4. **(Optional) Install restricted maintenance & operator shortcuts**:
   Configure `/usr/local/sbin/aoc-maintain` via [Maintenance helper](../deploy/maintenance/README.md) and copy `start.sh`, `stop.sh`, and `platformctl.py` to `~/aoc-ops/spark/`.
5. **Start the base station and platform**:
   ```sh
   ~/aoc-ops/spark/start.sh
   /usr/bin/python3 -I ~/aoc-ops/spark/platformctl.py status
   curl -fsS http://127.0.0.1:8877/api/v1/health
   ```

**Step 1 Pass Criteria**:
- All 12 `aoc-v2-open5gs` core containers are healthy.
- `aoc-v2-radio.service` and `aoc-v2-cpu-latency.service` are active, and Open5GS infoAPI confirms N2 NG Setup succeeded.
- `http://127.0.0.1:8877/api/v1/health` returns `ok`.

---

## Step 2 — Provision Open5GS Subscriber & Program TB01 SIM

1. **Confirm lab contract alignment**:
   Review [UE Access and Lab Policy](ue-access-policy.md) (`PLMN 460/03`, `DNN oai`, `SST 1`, `5QI 9`, IPv4 pool `10.0.0.0/24`).
2. **Register an independent subscriber in Open5GS**:
   Use `stacks/open5gs/subscriber.py` on Spark with an independent IMSI, Ki and OPc (`sqn=0`, single data PDU, `dnn=oai`, `sst=1`, `five_qi=9`). Never reuse an active card's identity on another UE.
3. **Program the TB01 blank USIM**:
   Follow [TB01 SIM Programming](sim-programming-tb01.md) using a PC/SC reader (`T=0`), verifying the card ATR, writing IMSI/Ki/OPc with **Milenage selector `00`**, and confirming readback + AUTS MAC-S match before ejecting the card.

**Step 2 Pass Criteria**:
- Open5GS reports the new active subscriber without altering existing subscribers.
- Card IMSI readback and local AUTS MAC-S match the private subscriber file; private material remains in `0700`/`0600` local storage outside Git.

---

## Step 3 — Deploy Jetson Console & Connect UE

1. **Install SIM & mount RM520N-GL on the Jetson carrier**:
   Mount the **Quectel RM520N-GL** module and insert the programmed TB01 Nano-SIM into the **[Waveshare SIM8262E-M2 5G for Jetson Orin](https://www.waveshare.net/shop/SIM8262E-M2-5G-for-Jetson-Orin.htm)** expansion board, attach the 4x 5G antennas, connect over USB 3.0 to **Jetson Orin**, and ensure `ModemManager` is stopped/disabled and NetworkManager leaves management Wi-Fi available (other defaults strictly above metric `10`).
2. **Build, install and commission Jetson Console (`0.6.2`)**:
   Follow [Jetson setup](setup-ue-jetson.md) (`make build-jetson-release`, `verify`, `preflight`, `sudo bash deploy/install-jetson.sh`), then stop services, run `commission` against Spark's management IP, and start:
   ```sh
   sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py stop
   sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py commission \
     --spark-address 192.0.2.20 --wifi-interface auto
   sudo /usr/bin/python3 -I -B /opt/agentic-ocudu/jetson/current/deploy/manage.py start
   ```
   *(Replace `192.0.2.20` with your Spark management address.)*
3. **Open Jetson Console over SSH tunnel & run Device Setup**:
   From your workstation:
   ```sh
   ssh -L 8878:127.0.0.1:8878 <user>@<jetson-host>
   ```
   Browse to `http://127.0.0.1:8878`, sign in, open **Device Setup**, review the planned PDU/network check, and run the setup workflow.

**Step 3 Pass Criteria**:
- `curl -fsS http://127.0.0.1:8878/api/v1/health` returns `ok`.
- **Overview** shows `SIM` ready, `NR SA` registered on `460/03`, active IPv4 PDU in `10.0.0.0/24`, `management_protected = true`, and a verified data path.

---

## Step 4 — End-to-End Verification & Optional Cold-Boot Auto-Connect

1. **Inspect Spark Platform over SSH tunnel**:
   ```sh
   ssh -L 8877:127.0.0.1:8877 <user>@<spark-host>
   ```
   Open `http://127.0.0.1:8877` and confirm **Overview**, **gNB**, **Core Network** and **Devices** show live metrics (`127.0.0.1:8879`), active UE context, matching PDU session, and fresh N3/N6/bridge counters.
2. **Verify dual-path protection on Jetson**:
   Confirm cellular traffic becomes the preferred IPv4 default (metric `10`) after two clean probe cycles while Wi-Fi management (`metric 5` fallback + Tailscale/SSH) remains reachable.
3. **(Optional) Enable unattended cold-boot connect**:
   Once manual bring-up is proven, follow the **Opt-in boot coordination** steps in [Jetson setup](setup-ue-jetson.md) to configure `boot_connect.py` and `aoc-v2-jetson-boot.service`, then validate with a real cold reboot.

---

## Next Steps

- **Daily console & lifecycle operations**: [Spark Operations](spark-operations.md) and [Jetson Operations](jetson-operations.md)
- **Fault diagnosis**: [Spark Troubleshooting](troubleshooting-bs-spark.md) and [Jetson Troubleshooting](troubleshooting-ue-jetson.md)
- **Custom AI development on reserved hardware headroom**: [DIY AI Customization](ai-customization.md)
