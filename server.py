import time

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, \
    QPushButton, QDialog, QLineEdit, QGridLayout

from communication import CommunicationChannel
from logger import logger
import csv

TIMETABLE = "timetable.csv"


class Window(QMainWindow):
    worktable = None

    def __init__(self):
        super(Window, self).__init__()
        self.setWindowTitle("Keep track of your workload!")

        self.channel = CommunicationChannel()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QHBoxLayout()
        central_widget.setLayout(self.layout)
        self._buttons = dict()
        buttons = (
            "Connection", "Read Tag", "Write Tag", "Download workload", "stop"
        )
        funcs = (
            self._connect, self._read, self._write, self._download,
            lambda: self.channel.send_command("stop", "update")
        )
        enabled = (True, False, False, False, False)
        for b, f, e in zip(buttons, funcs, enabled):
            self._make_button(b, f, e)

    def _make_button(self, name: str, func, set_enabled=True):
        button = QPushButton(name)
        button.clicked.connect(func)
        button.setEnabled(set_enabled)
        self.layout.addWidget(button)
        self._buttons[name] = button

    def _connect(self):
        logger.info("> Attempt connection")
        if self.channel.is_closed:
            try:
                self.channel.check_hand()
                self.channel.send_command("set_time", time.asctime())
                self._buttons["Connection"].setText("Disconnection")
                for b in self._buttons.values():
                    b.setEnabled(True)
                self._read()
            except (ConnectionError, ConnectionRefusedError):
                logger.warning("Connection failed")
        else:
            self.channel.disconnect()
            self._buttons["Connection"].setText("Connection")
            for b in self._buttons.values():
                b.setEnabled(b.text() == "Connection")

    def _read(self):
        self._buttons.get("Read Tag").setEnabled(False)
        self._buttons.get("Write Tag").setEnabled(True)
        self.channel.send_command("read", None)

    def _write(self):
        self._buttons.get("Read Tag").setEnabled(True)
        self._buttons.get("Write Tag").setEnabled(False)
        dialog = NameDialog()
        task_name = dialog.name
        if task_name is not None and not task_name == '':
            self.channel.send_command("write", task_name)

    def _download(self):
        self.channel.send_command("send", "")
        _, self.worktable = self.channel.read_sensor()
        logger.info(self.worktable)
        times, dates, indexes = self.worktable
        with open(TIMETABLE, 'w', newline='') as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=',')
            for task, date, duration in zip(indexes, dates, times):
                csv_writer.writerow([task, date, duration])


class NameDialog(QDialog):
    task_name = None

    def __init__(self, parent=None):
        super(NameDialog, self).__init__(parent)
        self.setWindowTitle("Enter new task")
        self.layout = QGridLayout()
        self.name_edit = QLineEdit()
        self.layout.addWidget(self.name_edit, 0, 0, 1, 2)
        self.setLayout(self.layout)
        accept_button = QPushButton("OK")
        accept_button.clicked.connect(self._set_name)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self._cancel)
        self.layout.addWidget(accept_button, 1, 0)
        self.layout.addWidget(cancel_button, 1, 1)
        self.exec()

    def _set_name(self):
        self.task_name = self.name_edit.text()
        self.close()

    def _cancel(self):
        self.close()

    @property
    def name(self):
        return self.task_name


def run():
    app = QApplication([])
    win = Window()
    win.show()
    app.exec()


if __name__ == '__main__':
    run()

    # channel = CommunicationChannel(side='PC')
    # channel.check_hand()
    # channel.send_command("send", "")
    # data = channel.read_sensor()
    # logger.info(data)
    # channel.disconnect()
