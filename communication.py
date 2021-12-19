import time
import pickle
import socket
import struct

from logger import logger
from bluetooth_manager import PCBluetoothManager, BoardBluetoothManager

_BT_PORT = 4


class BaseChannel:

    def __init__(self):
        # Will be set upon init
        self.is_PC = False
        self.connected = False

    def _send_object(self, name, value):
        raise NotImplementedError

    def _read_object(self, wait=True):
        raise NotImplementedError

    def send_sensor(self, name, value):
        if self.is_PC:
            raise Exception('PC cannot send sensor data')
        self._send_object(name, value)

    def send_command(self, name, value=None):
        if not self.is_PC:
            raise Exception('Robot cannot send motor data')
        return self._send_object(name, value)

    def read_sensor(self, wait=True) -> str:
        if not self.is_PC:
            raise Exception('Robot cannot read sensor data')
        return self._read_object(wait)

    def read_command(self):
        if self.is_PC:
            raise Exception('PC cannot read motor data')
        return self._read_object()

    def scan_bluetooth_devices(self):
        logger.info("default (fake) Bluetooth scan")
        addr_list = ['AA:AA:AA:AA:AA:AA', 'BB:BB:BB:BB:BB:BB']
        return addr_list


TIMEOUT_READ = 15


class CommunicationChannel(BaseChannel):

    def __init__(self, side='PC'):
        super(CommunicationChannel, self).__init__()

        # are we on the PC or robot side?
        self.side = side
        self.is_PC = side == 'PC'
        if self.is_PC:
            self.pc_bluetooth_manager = PCBluetoothManager()
        else:
            self.board_bluetooth_manager = BoardBluetoothManager()
        self._connection = None
        self._socket = None
        self._file = None
        self.send_lock = self.read_lock = self.check_hand_lock = False
        self.first_no_data_time = None
        self.ready = False

    def check_hand(self):
        self.ready = True

        # lock system
        if self.check_hand_lock:
            raise ConnectionError('channel already busy checking hand')
        logger.debug('channel - handcheck lock')

        mem_read_lock = self.read_lock
        self.check_hand_lock = self.read_lock = self.send_lock = True

        # connect and handle connection errors
        try:
            logger.info(f'Hand checking ({self.side} side)...')
            # hand checking: it is actually the PC that tries to connect the
            # robot, because only the robot has a fix IP address...
            if self.is_PC:
                # sensor stream
                # we check the protocol to create the right socket+
                self._connection = None
                b_mac = self.pc_bluetooth_manager.get_mac_address()
                _socket = socket.socket(
                    socket.AF_BLUETOOTH,
                    socket.SOCK_STREAM,
                    socket.BTPROTO_RFCOMM
                )

                sensor_address = (b_mac, _BT_PORT)
                _socket.settimeout(TIMEOUT_READ)
                _socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
                )
                try:
                    _socket.connect(sensor_address)
                    logger.info(' [connected]')
                except Exception as err:
                    _socket.close()
                    logger.warning(' [failed]')
                    logger.exception(err)
                    raise ConnectionRefusedError
                self._connection = _socket
                self._file = _socket.makefile('rwb')

                # motor stream
                time.sleep(.2)  # make sure the board has time to listen for
                # the second socket connection
                name, info = self._read_object(ignore_lock=True)
                # do stuff with name info
            else:
                _socket = socket.socket(
                    socket.AF_BLUETOOTH,
                    socket.SOCK_STREAM,
                    socket.BTPROTO_RFCOMM
                )
                _socket.bind(
                    (self.board_bluetooth_manager.mac, _BT_PORT)
                )

                _socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                _socket.listen(1)
                self._connection, _ = _socket.accept()
                _socket.close()
                self._file = self._connection.makefile('rwb')
                logger.info(' [accepted connection]')

                # motor stream

                # send info
                info = {
                    "task": "time",
                }
                self._send_object('checkhand info', info, ignore_lock=True)
                logger.info(' [sent checkhand info]')
            self.connected = True

        except Exception as err:
            # connection failed, cleanup sockets before raising error again
            self.cleanup()
            raise err

        finally:
            logger.debug('channel - handcheck unlock')
            self.check_hand_lock = self.send_lock = False
            self.read_lock = mem_read_lock
        logger.info(' [done]')
        logger.debug('[channel connected]')

    def disconnect(self):
        if self.connected:
            try:
                self.send_command('disconnect')
            except Exception as e:
                logger.exception(e)
            self.cleanup()
        else:
            logger.info("Channel already disconnected")

    def cleanup(self):
        logger.info(
            'Cleaning up communication channel ({} side)'.format(self.side)
        )
        self.ready = False
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._file is not None and not self._file.closed:
            try:
                self._file.close()
            except Exception as e:
                # not clear why we sometimes get an error here
                logger.exception(e)
            finally:
                self._file = None

    @property
    def is_closed(self):
        if self._file is not None:
            return self._file.closed
        else:
            return True

    def _send_object(self, name: str, value=None, ignore_lock=False):
        # lock system
        while not ignore_lock and self.send_lock:
            logger.warning('channel already busy sending data, wait')
            logger.debug('channel - sending locked, waiting')
            time.sleep(.1)
        logger.debug('channel - send lock (%s)' % name)
        self.send_lock = True

        # select channel
        f = self._file

        # send and handle connection errors
        try:
            # name
            x = str.encode(name)
            f.write(struct.pack('<H', len(x)))
            f.write(x)

            # value
            x = pickle.dumps(value)
            f.write(struct.pack('<L', len(x)))
            f.write(x)
            f.flush()
            return
        except ConnectionResetError:
            logger.warning("Connection lost while sending object")

        finally:
            if not ignore_lock:
                logger.debug('channel - send unlock')
                if name == 'disconnect':
                    self.connected = False
                self.send_lock = False

    def _read_object(self, wait=True, ignore_lock=False):
        # lock system
        while not ignore_lock and self.read_lock:
            logger.warning('channel already busy reading, wait')
            logger.debug('channel - read locked, waiting')
            time.sleep(.1)
        logger.debug('channel - read lock')
        self.read_lock = True
        # if we are aware that we are not connected
        if not self.connected and not ignore_lock:
            logger.debug(
                'attempted to read while not being connected, return None'
            )
            logger.debug('channel - read unlock')
            self.read_lock = False
            return '', None

        # select channel
        s = self._connection  # type: socket.socket
        f = self._file

        # read and handle connection errors
        try:
            # reading attempts: if failure, attempt to re-establish
            # connection, then second attempt if on PC side, or return
            # if on robot side

            # First attempt to read
            try:
                # no waiting: short timeout
                if not wait:
                    s.settimeout(.001)

                # name
                two_bytes = s.recv(2)
                if len(two_bytes) == 0:
                    raise ConnectionAbortedError
                if not wait:
                    # some data is available, so now wait until it is
                    # completely transmitted
                    s.settimeout(TIMEOUT_READ)
                n, = struct.unpack('<H', two_bytes)
                name = f.read(n).decode()

                # value
                four_bytes = f.read(4)
                if len(four_bytes) == 0:
                    raise ConnectionAbortedError
                n, = struct.unpack('<L', four_bytes)
                value = pickle.loads(f.read(n))
                # send receipt acknowledgment
                self.first_no_data_time = None
                return name, value

            except Exception as err:
                # remove timeout
                if not wait:
                    s.settimeout(TIMEOUT_READ)

                # no waiting: timeout just means that there is no data yet,
                # return as long as the first read attempt was no longer
                # than TIMEOUT_PC_READ before
                if not wait and isinstance(err, socket.timeout):
                    if self.first_no_data_time is None:
                        self.first_no_data_time = time.time()
                    if time.time() < self.first_no_data_time + TIMEOUT_READ:
                        return None

                # otherwise, there is a connection error
                raise err
        except ConnectionResetError:
            logger.warning("Connection lost while reading object")
            self.cleanup()
        finally:
            if not ignore_lock:
                self.read_lock = False
