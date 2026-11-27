"""Render an isolated core bundle using JSON (also valid YAML for OAI)."""

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets


NFS = ("nrf", "amf", "smf", "upf", "ausf", "udm", "udr")
SERVICES = ("mysql", *NFS, "ims", "ext-dn")


def private_write(path, content):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing to write through a symlink: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(content)


def write_json(path, value):
    private_write(path, json.dumps(value, indent=2) + "\n")


def check_images(lock):
    for name in SERVICES:
        item = lock[name]
        if item["architecture"] != "arm64" or not re.fullmatch(
                r"[a-z0-9./_-]+@sha256:[0-9a-f]{64}", item["reference"]):
            raise ValueError("An ARM64 digest-pinned image is required: " + name)


def nf_config(config, password):
    addr, radio = config["network"]["addresses"], config["radio"]
    plmn = radio["plmn"]
    if not re.fullmatch(r"[0-9]{5,6}", plmn):
        raise ValueError("PLMN must have five or six digits")
    snssai = {"sst": radio["sst"]}
    if radio.get("sd") is not None:
        snssai["sd"] = radio["sd"]
    slices = [{"sNssai": snssai, "dnnSmfInfoList": [{"dnn": "oai"}, {"dnn": "ims"}]}]
    nfs = {nf: {"host": addr[nf], "sbi": {"port": 8080, "api_version": "v1", "interface_name": "eth0"}}
           for nf in NFS}
    nfs["amf"]["n2"] = {"interface_name": "eth0", "port": 38412}
    for nf in ("smf", "upf"):
        nfs[nf]["n4"] = {"interface_name": "eth0", "port": 8805}
    for interface in ("n3", "n9"):
        nfs["upf"][interface] = {"interface_name": "eth0", "port": 2152}
    nfs["upf"]["n6"] = {"interface_name": "eth0"}
    return {
        "log_level": {"general": "info"}, "register_nf": {"general": True}, "http_version": 2,
        "nfs": nfs,
        "database": {"host": addr["mysql"], "user": "aoc", "type": "mysql", "password": password,
                     "database_name": "oai_db", "generate_random": True, "connection_timeout": 300},
        "amf": {"amf_name": "AOC-AMF", "relative_capacity": 30, "statistics_timer_interval": 20,
                "support_features_options": {"enable_simple_scenario": False, "enable_nssf": False,
                                             "enable_smf_selection": True},
                "emergency_support": False,
                "served_guami_list": [{"mcc": plmn[:3], "mnc": plmn[3:], "amf_region_id": "01",
                                       "amf_set_id": "001", "amf_pointer": "01"}],
                "plmn_support_list": [{"mcc": plmn[:3], "mnc": plmn[3:], "tac": radio["tac"], "nssai": [snssai]}],
                "supported_integrity_algorithms": ["NIA2", "NIA1", "NIA0"],
                "supported_encryption_algorithms": ["NEA0", "NEA2", "NEA1"]},
        "smf": {"ue_mtu": 1500,
                "support_features": {"use_local_subscription_info": True, "use_local_pcc_rules": True},
                "upfs": [{"host": addr["upf"], "config": {"enable_usage_reporting": True}}],
                "ue_dns": {"primary_ipv4": "8.8.8.8", "secondary_ipv4": "1.1.1.1"},
                "ims": {"pcscf_ipv4": addr["ims"]},
                "smf_info": {"sNssaiSmfInfoList": slices},
                "local_subscription_infos": [
                    {"single_nssai": snssai, "dnn": dnn,
                     "qos_profile": {"5qi": qi, "session_ambr_ul": "500Mbps", "session_ambr_dl": "1000Mbps"}}
                    for dnn, qi in (("oai", 9), ("ims", 5))]},
        "upf": {"support_features": {"enable_bpf_datapath": False, "enable_snat": True},
                "remote_n6_gw": "localhost", "smfs": [{"host": addr["smf"]}],
                "upf_info": {"sNssaiUpfInfoList": [{"sNssai": snssai,
                             "dnnUpfInfoList": [{"dnn": "oai"}, {"dnn": "ims"}]}]}},
        "dnns": [{"dnn": dnn, "pdu_session_type": "IPV4", "ipv4_subnet": subnet}
                 for dnn, subnet in config["network"]["ue_pools"].items()]}


def compose_config(config, lock):
    check_images(lock)
    addresses = config["network"]["addresses"]
    services = {}
    for name in SERVICES:
        addr_key = "ext_dn" if name == "ext-dn" else name
        services[name] = {"image": lock[name]["reference"], "platform": "linux/arm64",
                          "restart": "no", "networks": {"core": {"ipv4_address": addresses[addr_key]}},
                          "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}}}
    for nf in NFS:
        services[nf]["volumes"] = ["./nf.json:/openair-" + nf + "/etc/config.yaml:ro"]
        if nf != "nrf":
            services[nf]["depends_on"] = {"nrf": {"condition": "service_healthy"}}
    services["udr"]["depends_on"]["mysql"] = {"condition": "service_healthy"}
    services["mysql"].update({
        "environment": {"MYSQL_DATABASE": "oai_db", "MYSQL_USER": "aoc",
                        "MYSQL_PASSWORD_FILE": "/run/secrets/db_password",
                        "MYSQL_ROOT_PASSWORD_FILE": "/run/secrets/db_root_password"},
        "secrets": ["db_password", "db_root_password"],
        "volumes": ["mysql-data:/var/lib/mysql", "./schema.sql:/docker-entrypoint-initdb.d/00-schema.sql:ro"],
        "healthcheck": {"test": ["CMD-SHELL", "MYSQL_PWD=$$(cat /run/secrets/db_password) mysql -h 127.0.0.1 -u aoc oai_db -Nse 'SELECT COUNT(*) FROM AuthenticationSubscription' >/dev/null"],
                        "interval": "5s", "timeout": "5s", "retries": 40, "start_period": "30s"}})
    services["upf"].update({"cap_add": ["NET_ADMIN", "NET_RAW"], "devices": ["/dev/net/tun:/dev/net/tun"],
        "sysctls": {"net.ipv4.ip_forward": "1"},
        # The image's YAML-grep check cannot parse JSON and skips non-BPF port checks.
        "healthcheck": {"test": ["CMD-SHELL", "pidof oai_upf >/dev/null && " +
            "netstat -unl | grep -Fq '" + addresses["upf"] + ":2152 ' && " +
            "netstat -unl | grep -Fq '" + addresses["upf"] + ":8805 '"],
            "interval": "5s", "timeout": "5s", "retries": 20}})
    services["ext-dn"].update({"init": True, "cap_add": ["NET_ADMIN", "NET_RAW"],
        "entrypoint": ["/bin/sh", "/aoc/ext-dn.sh"],
        "volumes": ["./ext-dn.sh:/aoc/ext-dn.sh:ro"],
        "depends_on": {"upf": {"condition": "service_healthy"}},
        "healthcheck": {"test": ["CMD-SHELL", "pidof iperf3 >/dev/null"], "interval": "5s", "timeout": "3s", "retries": 10}})
    services["ims"].update({"volumes": ["./sip.conf:/etc/asterisk/sip.conf:ro", "./users.conf:/etc/asterisk/users.conf:ro",
                                                        "ims-data:/var/lib/asterisk"],
        "healthcheck": {"test": ["CMD-SHELL", "asterisk -rx 'core show uptime' | grep -q 'System uptime'"],
                        "interval": "5s", "timeout": "5s", "retries": 20}})
    plmn = config["radio"]["plmn"]
    services["ims"]["networks"]["core"]["aliases"] = [
        "ims.mnc{}.mcc{}.3gppnetwork.org".format(plmn[3:].zfill(3), plmn[:3])]
    return {"name": config["names"]["compose_project"], "services": services,
            "secrets": {name: {"file": "./secrets/" + name} for name in ("db_password", "db_root_password")},
            "volumes": {"mysql-data": {}, "ims-data": {}},
            "networks": {"core": {"name": config["names"]["docker_network"], "driver": "bridge",
                "driver_opts": {"com.docker.network.bridge.name": config["names"]["bridge"]},
                "ipam": {"config": [{"subnet": config["network"]["subnet"], "gateway": addresses["gnb"]}]}}}}


def schema_only(source):
    import sqlparse
    statements = [str(item).strip() for item in sqlparse.parse(source) if item.get_type() in ("CREATE", "ALTER")]
    if not statements or not any("`AuthenticationSubscription`" in item for item in statements):
        raise ValueError("Upstream SQL does not contain the required subscription schema")
    return "-- Generated from fixed OAI upstream schema; no sample subscribers.\n" + "\n\n".join(statements) + "\n"


def prepare(config, lock, output, schema):
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Bundle directory must be empty; never overwrite live config or passwords")
    if set(config["network"]["ue_pools"]) != {"oai", "ims"}:
        raise ValueError("This release requires exactly the oai and ims pools")
    compose = compose_config(config, lock)
    schema_text = schema_only(Path(schema).read_text())
    output.mkdir(parents=True, mode=0o700, exist_ok=True)
    output.chmod(0o700)
    password = secrets.token_hex(24)
    private_write(output / "secrets/db_password", password)
    private_write(output / "secrets/db_root_password", secrets.token_hex(24))
    write_json(output / "compose.json", compose)
    write_json(output / "nf.json", nf_config(config, password))
    private_write(output / "schema.sql", schema_text)
    # MySQL's entrypoint drops to its own UID before reading initialization SQL.
    (output / "schema.sql").chmod(0o644)
    plmn, addr = config["radio"]["plmn"], config["network"]["addresses"]
    domain = "ims.mnc{}.mcc{}.3gppnetwork.org".format(plmn[3:].zfill(3), plmn[:3])
    private_write(output / "sip.conf", "[general]\ncontext=default\nallowguest=no\nalwaysauthreject=yes\n"
                  "bindaddr={}\nbindport=5060\ntcpenable=no\nrealm={}\ndomain={}\n"
                  "disallow=all\nallow=alaw\nallow=ulaw\n".format(addr["ims"], domain, domain))
    private_write(output / "users.conf", "; No SIP accounts provisioned; SIP registration is outside this acceptance scope.\n")
    routes = ["ip route replace {} via {}".format(ipaddress.ip_network(pool), addr["upf"])
              for pool in config["network"]["ue_pools"].values()]
    private_write(output / "ext-dn.sh", "#!/bin/sh\nset -eu\n" + "\n".join(routes) +
                  "\nexec iperf3 -s -B {} -p 5201\n".format(addr["ext_dn"]))
    (output / "ext-dn.sh").chmod(0o644)
    write_json(output / "bundle.json", {"schema_version": 1, "project": config["names"]["compose_project"],
               "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
               "schema_source_sha256": hashlib.sha256(Path(schema).read_bytes()).hexdigest(),
               "subscribers_provisioned": False, "ims_kind": "Asterisk SIP service", "sip_registration_verified": False})
