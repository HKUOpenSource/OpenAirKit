import copy
from pathlib import Path
import tempfile
import unittest

from aoc_jetson.config import DEVICE
from aoc_jetson.hardware import discover


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sys_class = self.root / "class"
        for name in ("tty", "net"):
            (self.sys_class / name).mkdir(parents=True)
        self.config = {"device": copy.deepcopy(DEVICE)}

    def usb(self, name):
        usb = self.root / "devices" / name
        usb.mkdir(parents=True)
        (usb / "idVendor").write_text("2c7c\n")
        (usb / "idProduct").write_text("0801\n")
        return usb

    def interface(self, usb, number, driver):
        interface = usb / (usb.name + ":1." + str(number))
        interface.mkdir()
        (interface / "bInterfaceNumber").write_text(f"{number:02x}\n")
        target = self.root / "drivers" / driver
        target.mkdir(parents=True, exist_ok=True)
        (interface / "driver").symlink_to(target, target_is_directory=True)
        return interface

    def layout(self, usb, first_serial, data_number, driver="rndis_host", tty_base=0):
        for offset in range(4):
            interface = self.interface(usb, first_serial + offset, "option")
            port = interface / ("ttyUSB" + str(tty_base + offset))
            port.mkdir()
            entry = self.sys_class / "tty" / port.name
            entry.mkdir()
            (entry / "device").symlink_to(port, target_is_directory=True)
        interface = self.interface(usb, data_number, driver)
        entry = self.sys_class / "net" / ("modem" + str(tty_base))
        entry.mkdir()
        (entry / "device").symlink_to(interface, target_is_directory=True)

    def test_rndis_before_serial_selects_at_not_diag_even_with_renumbered_ttys(self):
        self.layout(self.usb("2-1"), 2, 0, tty_base=7)
        found = discover(self.config, self.sys_class)
        self.assertEqual(found["at_port"], "/dev/ttyUSB9")
        self.assertEqual(found["data_interface"], "modem7")

    def test_old_at_number_is_rejected_on_rndis_layout(self):
        self.layout(self.usb("2-1"), 2, 0)
        self.config["device"]["at_interface_number"] = "02"
        with self.assertRaisesRegex(ValueError, "expected 04"):
            discover(self.config, self.sys_class)

    def test_serial_before_data_uses_explicit_interface_02(self):
        self.layout(self.usb("2-1"), 0, 4, driver="cdc_ether")
        self.config["device"]["at_interface_number"] = "02"
        self.assertEqual(discover(self.config, self.sys_class)["at_port"], "/dev/ttyUSB2")

    def test_ecm_interface_0a_selects_at_interface_02(self):
        self.layout(self.usb("2-1"), 0, 0x0A, driver="cdc_ether")
        self.config["device"]["at_interface_number"] = "02"
        found = discover(self.config, self.sys_class)
        self.assertEqual(found["at_port"], "/dev/ttyUSB2")
        self.assertEqual(found["data_interface"], "modem0")
        self.config["device"]["at_interface_number"] = "04"
        with self.assertRaisesRegex(ValueError, "expected 02"):
            discover(self.config, self.sys_class)

    def test_unknown_serial_layout_is_rejected(self):
        self.layout(self.usb("2-1"), 3, 0)
        with self.assertRaisesRegex(ValueError, "Unsupported RM520N USB interface layout"):
            discover(self.config, self.sys_class)

    def test_second_matching_modem_is_rejected(self):
        self.layout(self.usb("2-1"), 2, 0)
        self.layout(self.usb("2-2"), 2, 0, tty_base=4)
        with self.assertRaisesRegex(ValueError, "Multiple matching modems"):
            discover(self.config, self.sys_class)

    def test_unrelated_usb_network_cannot_supply_missing_data_interface(self):
        modem = self.usb("2-1")
        self.layout(modem, 2, 0)
        (self.sys_class / "net/modem0/device").unlink()
        other = self.usb("2-2")
        interface = self.interface(other, 0, "rndis_host")
        (self.sys_class / "net/modem0/device").symlink_to(interface, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "unique RM520N data interface"):
            discover(self.config, self.sys_class)


if __name__ == "__main__":
    unittest.main()
