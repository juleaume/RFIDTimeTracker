# -- coding: utf-8 --
import os.path
import socket
import subprocess
import sys
import pickle

import RPi.GPIO as GPIO
from pirc522 import RFID
import time
import threading

from communication import CommunicationChannel
from logger import logger
from bluetooth_manager import BoardBluetoothManager

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

debug_uid = str([136, 4, 114, 215, 41])

LOOKUP_FILE = "lookup_table.pkl"
if not os.path.isfile(LOOKUP_FILE):
    with open(LOOKUP_FILE, 'wb') as lookup_file:
        pickle.dump({debug_uid: "DEBUG"}, lookup_file)

ACTIVITY_TABLE = "activity_table.pkl"
if not os.path.isfile(ACTIVITY_TABLE):
    with open(ACTIVITY_TABLE, 'wb') as activity_file:
        pickle.dump(([], [], []), activity_file)


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
    with open(LOOKUP_FILE, 'rb') as f:
        _lookup_table = pickle.load(f)
    with open(ACTIVITY_TABLE, 'rb') as f:
        _activity_tuple = pickle.load(f)
        print(_activity_tuple)
    _activity_table, _absolute_time_table, _index_table = _activity_tuple

    is_reading = True
    is_updating = True
    is_writing = False

    def __init__(self):
        # setup bluetooth
        self.channel = CommunicationChannel(side='Board')
        self._read_thread = None
        self._update_time_thread = None
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

    def run(self):
        while True:
            try:
                while True:
                    logger.info("> Checking hand")
                    self.channel.check_hand()
                    if self.channel.connected:
                        logger.info("> Connected")
                        break
                while not self.channel.is_closed:
                    logger.info("reading command")
                    _command = self.channel.read_command()
                    logger.info(_command)
                    if _command is not None:
                        name, value = _command
                    else:
                        continue
                    if name == "read":
                        if not self.is_reading:
                            self.start_reading()
                    elif name == "write":
                        self._write(value)
                    elif name == "send":
                        self._send_data()
                    elif name == "stop":
                        if value == "update":
                            self.stop_updating()
                            self.start_reading()
                        elif value == "read":
                            self.stop_reading()
                        else:
                            sys.exit(0)
                    elif name == "disconnect":
                        self.channel.cleanup()
                    elif name == "set_time":
                        logger.info(f"setting time to {value}")
                        subprocess.call(["sudo", "date",  "-s", value])
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
            logger.info("> Waiting to read new tag")
            uid = self._read_tag()  # blocking call
            if not self.is_reading:  # check if still reading
                break
            if uid is not None:
                if not uid == self._last_id:
                    self.record_new_activity(uid)
            time.sleep(1)

    def _write(self, task):
        self.stop_updating()
        self.stop_reading()
        logger.info(f"> Waiting for new tag to write {task}")
        uid = self._read_tag()
        if uid is not None:
            self._record_new_task(uid, task)

    def _read_tag(self):
        self.rc522.wait_for_tag()  # blocking call
        error, tag_type = self.rc522.request()
        if not error:
            error, uid = self.rc522.anticoll()
            if not error:
                if str(uid) not in self._lookup_table.keys():
                    logger.info(f"unknown tag: {uid}")
                # if uid == debug_uid:
                #     self.__debug_record()
                return uid
        return None

    def _send_data(self):
        if self.channel is not None and not self.channel.is_closed:
            self.channel.send_sensor(
                "data", self.data
            )

    @property
    def data(self):
        return (
            self._activity_table,
            self._absolute_time_table,
            self._index_table
        )

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
        with open(LOOKUP_FILE, 'wb') as f:
            pickle.dump(self._lookup_table, f)  # save the new uuid
        self._last_id = None
        logger.info(f"New task registered: {task}")

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
        self._absolute_time_table.append(time.asctime())
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
            logger.debug(
                f"update time of {self._lookup_table.get(str(self._last_id))}"
            )
            self._activity_table[-1] = int(time.time() - self._tic_task)
            with open(ACTIVITY_TABLE, 'wb') as f:
                pickle.dump(self.data, f)
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
    try:
        client = Client()
        client.run()
    except Exception as e:
        logger.exception(e)
    finally:
        logger.info("stopping device")
