#  Use to get the list of paired devices on the user computer.
#  Depending on with OS we can use the same methode.

import platform  # use to find out the user's OS
import subprocess

from logger import logger

import bluetooth

NAME = 'RFIDTIMETRACKER'


class PCBluetoothManager:
    _bluetooth_paired_devices = []

    def __init__(self):
        self.get_paired_devices()

    def get_paired_devices(self):
        #  we set the duration to 1 to get a fast search, we only get the
        #  already paired devices. We want the name and the address but
        #  not the class.
        for device in bluetooth.discover_devices(
                duration=1, lookup_names=True, lookup_class=False
        ):
            address, name = device
            if NAME in name.upper():
                self._bluetooth_paired_devices.append(
                    f'{name} | {address}'
                )

    # the other function are identical in linux and windows

    def get_mac_address(self):  # we use the name to find the
        # address
        logger.debug("get mac address from name")
        for device in self._bluetooth_paired_devices:
            if NAME in device:
                return device[16:33]

    def get_all_paired_device_address(self):  # we extract the address
        logger.debug("extract address")
        addresses = []
        for device in self._bluetooth_paired_devices:
            addresses.append(device[16:33])
        return addresses

    def get_all_paired_device_names(self) -> list:  # we extract the name
        logger.debug("extract name")
        name = []
        for device in self._bluetooth_paired_devices:
            name.append(device[0:13])
        return name


class BoardBluetoothManager:
    def __init__(self):
        # Discoverable on
        command = ['sudo', 'hciconfig', 'hci0', 'piscan']
        subprocess.check_output(command, stderr=subprocess.STDOUT)
        # Setting up the new name from the ssid
        open_blue = subprocess.Popen(
            ["bluetoothctl"],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE
        )
        open_blue.communicate(f"system-alias {NAME}".encode('ascii'))
        logger.info('Bluetooth has been updated')
        command = ["cat", "/sys/kernel/debug/bluetooth/hci0/identity"]
        output = subprocess.check_output(
            command, stderr=subprocess.STDOUT).decode()[0:17]
        self._mac = output

    @property
    def mac(self):
        return self._mac
