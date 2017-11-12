# Joe Mynhier 26 April 2017

# This program was written for the CAT project on
# the DKC team in Purdue's EPICS Program.
#
# This program reads data from two Bluetooth modems.
# Each modem sends data on the degree of flex of
# five fingers. This program uses a GUI to display
# that data for debugging purposes.

# See here for enabling Bluetooth access:
# https://raspberrypi.stackexchange.com/questions/41776/failed-to-connect-to-sdp-server-on-ffffff000000-no-such-file-or-directory


import bluetooth as bt
from time import sleep
import sys
import threading
import PyQt4.QtGui as QtGui
import PyQt4.QtCore as QtCore
import numpy as np
from enum import Enum

#DEBUG
import struct


# This enum allows unique finger identification
class Finger(Enum):

    RThumb = 0
    RPointer = 1
    RMiddle = 2
    RRing = 3
    RPinky = 4
    LThumb = 5
    LPointer = 6
    LMiddle = 7
    LRing = 8
    LPinky = 9


# This function returns a finger enum. It takes hand,
# either "r" or "l" and the raw integer data from the
# Bluetooth.
def get_finger(hand, data):

    finger_id = data >> 12
    if hand == 'r':
        offset = 0
    else:
        offset = 5
    return Finger(finger_id + offset)


# This class wraps data that is written from the
# Bluetooth thread and read via pyqtSignal in
# another thread that runs the GUI.
class GlobalWrapper(QtCore.QObject):

    changed = QtCore.pyqtSignal(Finger)

    def __init__(self):
        super(GlobalWrapper, self).__init__( )

        self._val = {finger_id: 0 for finger_id in Finger}

    # Stores data. data is the raw data, hand is "r" or "l"
    def set_val(self, hand, data):

        try:

            finger_id = get_finger(hand, data)

            print("data ({}, {:0x})".format(finger_id, data & 0xfff))
            self._val[finger_id] = data & 0xfff
            self.changed.emit(finger_id)

        except ValueError as ve:
            print(ve)

    # overload [] operator. Returns data for particular Finger enum.
    def __getitem__(self, item):
        return self._val[item]


global_data = GlobalWrapper()


# This class executes GUI elements. It initializes
# the display, sets up the custom slot used to
# process data from global_data and connects
# the slot to global_data's signal.
class Display(QtGui.QWidget, QtCore.QObject):

    def __init__(self):

        super(Display, self).__init__()

        # Load background image
        self.background = QtGui.QImage("gui_background_short.jpg")

        # Set up bars
        self.bar_width = 22
        self.bar_heights = {finger_id: h for (finger_id, h) in
                            zip(Finger, [134, 227, 235, 202, 165, 134, 227, 235, 202, 165])}
        self.bar_color = 0x4051f6
        self.bar_arrays = {finger_id: np.full((self.bar_heights[finger_id], self.bar_width),
                                              self.bar_color, dtype=np.int32) for finger_id in Finger}

        bar_images = {finger_id: QtGui.QImage(self.bar_arrays[finger_id], self.bar_arrays[finger_id].shape[1],
                                       self.bar_arrays[finger_id].shape[0], 4*self.bar_arrays[finger_id].shape[1],
                                       QtGui.QImage.Format_RGB32) for finger_id in Finger}

        # Paint bars on image
        self.bar_x = {finger_id: x for (finger_id, x) in
                      zip(Finger, [563, 628, 694, 773, 843, 380, 316, 250, 171, 100])}
        self.bar_y = {finger_id: y for (finger_id, y) in
                      zip(Finger, [318, 53, 45, 78, 115, 318, 53, 45, 78, 115]) }
        painter = QtGui.QPainter()
        painter.begin(self.background)
        for finger_id in Finger:
            painter.drawImage(self.bar_x[finger_id], self.bar_y[finger_id], bar_images[finger_id])

        painter.end()

        # Display the image
        self.label = QtGui.QLabel()
        self.label.setPixmap(QtGui.QPixmap.fromImage(self.background))
        self.image_layout = QtGui.QGridLayout( )
        self.image_layout.addWidget(self.label, 0, 0)

        # Set up window
        self.setGeometry(0, 0, self.background.width( ), self.background.height( ))
        self.setWindowTitle("Glove Test")

        global_data.changed.connect(self.image_update)

        # Display
        self.setLayout(self.image_layout)
        self.show( )

    # When global_data emits its signal, this slot
    # processes the data.
    @QtCore.pyqtSlot(Finger)
    def image_update(self, finger_id):

        # Draw the bar proportionally from the bottom.
        val = self.bar_heights[finger_id] - (self.bar_heights[finger_id] *
                                       global_data[finger_id]) // (0xfff)
        self.bar_arrays[finger_id][0:val, :].fill(0xffffffff)
        self.bar_arrays[finger_id][val:, :].fill(self.bar_color)

        # update the GUI
        # make new image
        h, w = self.bar_arrays[finger_id].shape
        image = QtGui.QImage(self.bar_arrays[finger_id], w, h, 4 * w, QtGui.QImage.Format_RGB32)
        # Paint onto background
        painter = QtGui.QPainter()
        painter.begin(self.background)
        painter.drawImage(self.bar_x[finger_id], self.bar_y[finger_id], image)
        painter.end( )
        # Redraw display
        self.label.setPixmap(QtGui.QPixmap.fromImage(self.background))
        self.show()

    # Close GUI when Esc is pressed
    def keyPressEvent(self, event):

        if event.key( ) == QtCore.Qt.Key_Escape:
            self.close( )


# main GUI startup
def run_gui( ):

    app = QtGui.QApplication(sys.argv)
    display = Display( )
    app.exec_( )


# A thread with a safe stop method that runs the Bluetooth connection
class ClientThread(threading.Thread):

    def __init__(self, args):

        super(ClientThread, self).__init__(target=self._client_thread, args=args)
        self._end_control = threading.Event( )

    def end(self):

        self._end_control.set( )

    def end_is_set(self):

        return self._end_control.is_set()

    # This function processes a client thread for the
    # Bluetooth connection. All it does is take user data from
    # the glove and store it in an instance of
    # global_wrapper.
    def _client_thread(self, mac_addr, port, hand):

        if hand == 'l':
            hand_name = "left"
        else:
            hand_name = "right"

        socket = bt.BluetoothSocket(bt.RFCOMM)
        socket.connect((mac_addr, port))
        print("Connected with {} glove {}:{}".format(hand_name, mac_addr, port))

        raw_data = []

        try:

            while not self.end_is_set():

                socket.send(str.encode('S'))

                # Grab a data frame.
                raw_data.extend(memoryview(socket.recv(16)).tolist())
                print("raw: {}".format(raw_data))

                while len(raw_data) > 1:

                    # convert data to an integer value.
                    msb = raw_data.pop()
                    lsb = raw_data.pop()
                    data = lsb | msb << 8

                    # store data.
                    global_data.set_val(hand, data)

        except bt.BluetoothError as BE:

            print("Connection lost with {} glove", hand_name)
            raise BE

        finally:

            socket.close( )


if __name__ == "__main__":

    # Spawn GUI thread
    t1 = threading.Thread(target=run_gui)
    t1.start( )

    try:

        # Connect Bluetooth
        #right_service = bt.find_service(address="00:06:66:8C:D3:66")
        right_thread = ClientThread(args=("00:06:66:8C:D3:66", 1, "r"))

        #left_service = bt.find_service(address="")
        #left_thread = ClientThread(args=(left_service["host"], left_service["port"], "l"))

        right_thread.start( )
        #left_thread.start( )

    except bt.BluetoothError as BE:

        print("{}", BE.args)

    finally:

        # wait for GUI to quit
        t1.join( )

        right_thread.end( )
        #left_thread.end( )
        right_thread.join( )
        #left_thread.join( )

        print("Connections closed")
