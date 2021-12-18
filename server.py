from PyQt5.QtWidgets import QApplication, QMainWindow


class Window(QMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        self.setWindowTitle("Keep track of your workload!")


if __name__ == '__main__':
    app = QApplication([])
    win = Window()
    win.show()
    app.exec()
