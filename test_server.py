# Joe Mynhier 7 April 2017
# This program is a proof of concept using a basic socket
# server to provide data for a GUI that runs in parallel
# to it. The server is standing in for the asynchronous
# signals that the final program will receive from
# Bluetooth.


import socket
import sys
from threading import Thread
import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore
import numpy as np


# This class wraps integer data that is written from a
# thread running a server and read via pyqtSignal in
# another thread that runs the GUI.
class global_wrapper(QtCore.QObject):
    changed = QtCore.pyqtSignal()

    def __init__(self):
        super(global_wrapper, self).__init__( )

        self._val = 0

    def set_val(self, val):
        self._val = val
        self.changed.emit()

    def get_val(self):
        return self._val


global_data = global_wrapper()


# This function processes a client thread for the
# socket server. All it does is take user data from
# the client and store it in an instance of
# global_wrapper.
def client_thread(conn):
    conn.send(b"Welcome to the server. Enter a value between 1 and 100 and press ENTER.\n")

    while True:
        data = conn.recv(1024)

        if not data:
            # connection severed
            break

        # convert data to an integer value.
        str_data = data.decode('utf-8').strip()

        # confirm data recieved.
        reply = "Heard: '" + str_data + "'\n"
        conn.sendall(reply.encode('utf-8'))

        # store data.
        global_data.set_val(int(str_data))


# This class executes GUI elements. It initializes
# the display, sets up the custom slot used to
# process data from global_data and connects
# the slot to global_data's signal.
class Display(QtGui.QWidget, QtCore.QObject):
    
    def __init__(self):
        super(Display, self).__init__( )

        self.setGeometry(300, 300, 100, 300)
        self.setWindowTitle("Glove Test")

        # create initial image
        self.image_array = np.full((300,100), 0xffffffff, dtype=np.int32)
        self.qimage = QtGui.QImage(self.image_array, 100, 300, 4*100, QtGui.QImage.Format_RGB32)

        self.label = QtGui.QLabel(self)
        self.label.setPixmap(QtGui.QPixmap(self.qimage))
        self.label.move(0, 0)

        # quit button

        # self.connect(global_data, global_data.changed(), self.image_update())
        global_data.changed.connect(self.image_update)

        self.show()
        self.label.show()

    # When global_data emits its singal, this slot
    # processes the data.
    @QtCore.pyqtSlot( )
    def image_update(self):
            # Draw the bar proportionally from the bottom.
            val = 300 - 3*global_data.get_val()
            self.image_array[0:val,:].fill(0xffffffff)
            self.image_array[val:300,:].fill(0x0000008B)

            # update the GUI
            self.qimage = QtGui.QImage(self.image_array, 100, 300, 4*100, QtGui.QImage.Format_RGB32)
            self.label.setPixmap(QtGui.QPixmap(self.qimage))
            self.show()
            self.label.show()


# main GUI startup
def run_gui( ):
    app = QtGui.QApplication(sys.argv)
    display = Display()
    sys.exit(app.exec_())



if __name__ == "__main__":

    # spawn a separate thread for the GUI
    Thread(target=run_gui).start()

    # Initialize socket server
    HOST = ''
    PORT = 8888

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Bind server to localhost:8888
    try:
        s.bind((HOST,PORT))
    except socket.error as s_err:
        print("Bind failed. Error code : {} Message {}".format(s_err.errno, s_err))
        sys.exit()

    print("Socket bind complete")

    s.listen(10)
    print("Socket listening")
    while True:
        # spawn client threads
        conn, addr = s.accept()
        print("Connected with {}:{}".format(addr[0], addr[1]))
        Thread(target=client_thread, args=(conn,)).start()