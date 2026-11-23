"""Read-only USB topology discovery shared by the executor and preflight."""
from pathlib import Path


def usb_parent(path):
    node = path.resolve(strict=True)
    for parent in (node, *node.parents):
        if (parent / "idVendor").exists() and (parent / "idProduct").exists():
            return parent
    raise ValueError("USB parent could not be established")


def interface_number(path):
    node = path.resolve(strict=True)
    interface = next((parent for parent in (node, *node.parents)
                      if (parent / "bInterfaceNumber").exists()), None)
    return (interface / "bInterfaceNumber").read_text().strip() if interface else None


def discover(config, sys_class=Path("/sys/class"), dev_root=Path("/dev")):
    device = config["device"]
    expected = (device["usb_vendor_id"], device["usb_product_id"])
    ports = []
    root = None
    for tty in sorted((sys_class / "tty").glob("ttyUSB*")):
        parent = usb_parent(tty / "device")
        identity = ((parent / "idVendor").read_text().strip(),
                    (parent / "idProduct").read_text().strip())
        if identity != expected:
            continue
        root = parent if root is None else root
        if parent != root:
            raise ValueError("Multiple matching modems are present")
        ports.append({"path": str(dev_root / tty.name),
                      "interface_number": interface_number(tty / "device")})
    if root is None:
        raise ValueError("A unique RM520N AT interface was not found")
    networks = []
    for interface in sorted((sys_class / "net").iterdir()):
        driver = interface / "device/driver"
        if driver.exists() and driver.resolve().name in ("rndis_host", "cdc_ether"):
            if usb_parent(interface / "device") == root:
                networks.append({"name": interface.name,
                                 "interface_number": interface_number(interface / "device")})
    if len(networks) != 1:
        raise ValueError("A unique RM520N data interface was not found")
    # RNDIS can occupy USB interfaces 00/01, shifting the four serial functions
    # (DIAG, GNSS, AT, modem) to 02..05. ECM (cdc_ether) places serial functions
    # at 00..03 (AT at 02) and the data interface at 04 or 0a. Never open DIAG
    # using the wrong AT number.
    layouts = {("00", ("02", "03", "04", "05")): "04",
               ("04", ("00", "01", "02", "03")): "02",
               ("0a", ("00", "01", "02", "03")): "02"}
    numbers = tuple(sorted(item["interface_number"] or "" for item in ports))
    expected_at = layouts.get((networks[0]["interface_number"], numbers))
    if expected_at is None:
        raise ValueError("Unsupported RM520N USB interface layout")
    if device["at_interface_number"] != expected_at:
        raise ValueError("Configured AT interface differs from USB layout; expected " + expected_at)
    at = [item for item in ports if item["interface_number"] == expected_at]
    return {"at_port": at[0]["path"], "data_interface": networks[0]["name"],
            "serial_port_count": len(ports), "usb_identity": ":".join(expected)}
