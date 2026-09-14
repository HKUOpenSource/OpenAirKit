"""Compare live network resources with the selected environment."""

import ipaddress

from scripts.validate import endpoints_overlap, validate


def inspect(config, inventory, radio=False, *, scope="deployment"):
    if scope not in ("deployment", "radio"):
        raise ValueError("Unknown preflight scope")
    errors = validate(config)
    if inventory.get("architecture") != "aarch64":
        errors.append("Target must be Linux ARM64")
    for field in ("routes", "addresses", "networks", "listeners", "units"):
        if not inventory.get(field, {}).get("ok"):
            errors.append("Required inventory failed: " + field)
    if errors:
        return errors
    desired = [ipaddress.ip_network(config["network"]["subnet"])]
    desired += [ipaddress.ip_network(value) for value in config["network"]["ue_pools"].values()]
    own_bridge = None
    for network in inventory["networks"]["data"]:
        owned = (network.get("Labels") or {}).get("com.docker.compose.project") == config["names"]["compose_project"]
        if owned and network["Name"] == config["names"]["docker_network"]:
            pools = network.get("IPAM", {}).get("Config", [])
            if (len(pools) != 1 or pools[0].get("Subnet") != config["network"]["subnet"] or
                    pools[0].get("Gateway") != config["network"]["addresses"]["gnb"] or
                    (network.get("Options") or {}).get("com.docker.network.bridge.name") != config["names"]["bridge"]):
                errors.append("Existing project network differs from the configured network")
            else:
                own_bridge = config["names"]["bridge"]
                continue
        if network["Name"] == config["names"]["docker_network"]:
            errors.append("Docker network name is owned by another project")
        for pool in network.get("IPAM", {}).get("Config", []) or []:
            if not pool.get("Subnet"):
                continue
            subnet = ipaddress.ip_network(pool["Subnet"])
            if any(subnet.version == item.version and subnet.overlaps(item) for item in desired):
                errors.append("Docker subnet conflict: " + str(subnet))
    for route in inventory["routes"]["data"]:
        destination = route.get("dst", "default")
        if destination == "default":
            continue
        subnet = ipaddress.ip_network(destination, strict=False)
        if route.get("dev") == own_bridge and subnet.subnet_of(desired[0]):
            continue
        if any(subnet.overlaps(item) for item in desired):
            errors.append("Host route conflict: " + str(subnet))
    for link in inventory["addresses"]["data"]:
        if link["ifname"] == config["names"]["bridge"] and own_bridge is None:
            errors.append("Bridge interface exists without project ownership")
    # ss -H -lntup: protocol, state, recv-q, send-q, local endpoint, peer endpoint.
    for line in inventory["listeners"]["data"].splitlines():
        columns = line.split()
        if len(columns) < 6 or columns[0] not in ("tcp", "udp"):
            errors.append("Cannot interpret listener: " + line)
            continue
        address, port = columns[4].rsplit(":", 1)
        if not port.isdigit():
            errors.append("Cannot interpret listener port")
            continue
        address = address.strip("[]").split("%", 1)[0]
        endpoint = {"protocol": columns[0], "address": "::" if address == "*" else address, "port": int(port)}
        for planned in config["listeners"]:
            # The independently deployed monitor is not bound by radio lifecycle commands.
            if scope == "radio" and planned["name"] == "monitor_web":
                continue
            if endpoints_overlap(endpoint, planned):
                errors.append("Listener conflict: {}:{} for {}".format(address, port, planned["name"]))
    if radio:
        if not inventory.get("sudo", {}).get("ok"):
            errors.append("System service installation/start requires sudo")
        if not config["radio"].get("validated"):
            errors.append("RF parameters have not been validated")
        for key in ("serial", "dl_arfcn", "tx_gain", "rx_gain"):
            if config["radio"].get(key) is None:
                errors.append("Missing RF parameter: " + key)
        units = inventory["units"]["data"].split("\n\n")
        for unit in units:
            if "Id=oai-ext-dn-iperf3.service" in unit and "ActiveState=active\n" not in unit + "\n":
                errors.append("External iperf service is unhealthy; site rollback is not ready")
    return errors
