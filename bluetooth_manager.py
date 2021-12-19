#  Use to get the list of paired devices on the user computer.
#  Depending on with OS we can use the same methode.

import subprocess

import bluetooth

from logger import logger

NAME = 'RFIDTIMETRACKER'


class PCBluetoothManager:
    _bluetooth_paired_devices = dict()

    def __init__(self):
        #  we set the duration to 1 to get a fast search, we only get the
        #  already paired devices. We want the name and the address but
        #  not the class.
        for device in bluetooth.discover_devices(
                duration=1, lookup_names=True, lookup_class=False
        ):
            address, name = device
            if NAME in name.upper():
                self._bluetooth_paired_devices[name] = address

    @property
    def name_mac(self):
        return self._bluetooth_paired_devices

    def get_mac_address(self):
        return self.name_mac.get(NAME, None)

    @property
    def macs(self):
        return self.name_mac.values()

    @property
    def names(self) -> list:  # we extract the name
        return list(self.name_mac.keys())


class BoardBluetoothManager:
    def __init__(self):
        # self._make_discoverable()
        subprocess.run(["bluetoothctl", "power", "on"])
        subprocess.run(["bluetoothctl", "discoverable", "on"])
        subprocess.run(["bluetoothctl", "pairable", "on"])
        logger.info('Bluetooth has been updated')
        command = ["cat", "/sys/kernel/debug/bluetooth/hci0/identity"]
        output = subprocess.check_output(
            command, stderr=subprocess.STDOUT).decode()[0:17]
        self._mac = output

    @property
    def mac(self):
        return self._mac
