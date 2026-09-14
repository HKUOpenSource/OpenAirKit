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
    at = [item for item in ports if item["interface_number"] == device["at_interface_number"]]
    if len(at) != 1 or root is None:
        raise ValueError("A unique RM520N AT interface was not found")
    networks = []
    for interface in sorted((sys_class / "net").iterdir()):
        driver = interface / "device/driver"
        if driver.exists() and driver.resolve().name in ("rndis_host", "cdc_ether"):
            if usb_parent(interface / "device") == root:
                networks.append(interface.name)
    if len(networks) != 1:
        raise ValueError("A unique RM520N data interface was not found")
    return {"at_port": at[0]["path"], "data_interface": networks[0],
            "serial_port_count": len(ports), "usb_identity": ":".join(expected)}
