# -- coding: utf-8 --
import socket

import RPi.GPIO as GPIO
from pirc522 import RFID
import time
import threading

from communication import CommunicationChannel
from logger import logger
from bluetooth_manager import BoardBluetoothManager

GPIO.setmode(GPIO.BOARD)  # Définit le mode de numérotation (Board)
GPIO.setwarnings(False)  # On désactive les messages d'alerte

debug_uid = [136, 4, 114, 215, 41]


class Client:
    """
    Client class to record the time using NFC tags. The tasks are in a lookup
    table to match an uid with a human-readable task. Each task of the session
    and its associated time are stored in two different lists, sharing the same
    index, to indicate the number of tasks in the current session. As long as
    the tag does not change, the time increases, even if the tag is removed !
    """
    rc522 = RFID()
    _last_id = None
    _tic_task = -float('inf')  # start of the task
    # _lookup_table = dict()
    _lookup_table = {
        "[89, 26, 210, 178, 35]": "testing",
        "[25, 54, 10, 163, 134]": "changing"

    }
    _activity_table = list()
    _index_table = list()

    is_reading = True
    is_updating = True
    is_writing = False

    def __init__(self):
        # setup bluetooth
        self.bluetooth_manager = BoardBluetoothManager()
        self.channel = CommunicationChannel(side='Board')
        self._read_thread = None
        self._update_time_thread = None
        self._connection_thread = threading.Thread(target=self._run)
        self._connection_thread.start()
        self.start_reading()

    def stop_reading(self):
        self.is_reading = False
        if self._read_thread is not None and self._read_thread.is_alive():
            self._read_thread.join()

    def start_reading(self):
        self.stop_reading()
        self.is_reading = True
        self._read_thread = threading.Thread(target=self._read)
        self._read_thread.start()

    def _run(self):
        while True:
            try:
                while True:
                    self.channel.check_hand()
                    if self.channel.connected:
                        logger.info("> Connected")
                        break
                while not self.channel.is_closed:
                    _command = self.channel.read_command()
                    if _command is not None:
                        name, value = _command
                    else:
                        continue
                    if name == "read":
                        if not self.is_reading:
                            self.start_reading()
                    elif name == "write":
                        self._write(value)
            except KeyboardInterrupt:
                break
            except socket.timeout:
                logger.warning("timeout")
            except Exception as e:
                logger.exception(e)
                break
            finally:
                if self.channel is not None:
                    self.channel.cleanup()

    def _read(self):
        while self.is_reading:
            logger.info("> Waiting")
            uid = self._read_tag()
            if uid is not None:
                if not uid == self._last_id:
                    self.record_new_activity(uid)
            time.sleep(1)

    def _write(self, task):
        self.stop_reading()
        logger.info("> Waiting")
        uid = self._read_tag()
        if uid is not None:
            self._record_new_task(uid, task)
        self.start_reading()

    def _read_tag(self):
        self.rc522.wait_for_tag()  # blocking call
        error, tag_type = self.rc522.request()
        if not error:
            error, uid = self.rc522.anticoll()
            if not error:
                if str(uid) not in self._lookup_table.keys():
                    logger.info(f"tag: {uid}")
                if uid == debug_uid:
                    self.__debug_record()
                return uid
        return None

    def __debug_record(self):
        time.sleep(10)
        self._write("test_write")

    def _record_new_task(self, uid: list, task: str):
        """
        Adds a new task by matching an uid to its name
        :param uid: the uid of the tag
        :param task: the task it is associated to
        :return:
        """
        self._lookup_table[str(uid)] = task

    def record_new_activity(self, uid: list):
        """
        starts a new task
        :param uid: the uid of the tag to start the task
        :return:
        """
        task = self._lookup_table.get(str(uid), None)
        if task is None:  # known tag?
            logger.warning(f"No task registered for tag {uid}")
            return
        logger.info(f"Starting task {task}")
        self.stop_updating()
        self._index_table.append(task)
        self._activity_table.append(0)
        self._last_id = uid
        self._tic_task = time.time()
        self._update_time_thread = threading.Thread(
            target=self.update_activity_time)
        self._update_time_thread.start()

    def update_activity_time(self):
        """
        update the activity with a ping of 1s
        :return:
        """
        self.is_updating = True
        while self.is_updating:
            logger.info(
                f"update time of {self._lookup_table.get(str(self._last_id))}"
            )
            self._activity_table[-1] = time.time() - self._tic_task
            time.sleep(1)
        logger.info("Updating stopped")

    def stop_updating(self):
        self.is_updating = False
        if self._update_time_thread is not None \
                and self._update_time_thread.is_alive():
            self._update_time_thread.join()

    def __del__(self):
        if self.channel is not None and self.channel.ready:
            self.channel.cleanup()
        self.rc522.cleanup()


if __name__ == '__main__':
    client = Client()
