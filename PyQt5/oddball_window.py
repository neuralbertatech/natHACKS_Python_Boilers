'''
This is the oddball task
- it displays either a blue or green circle and records when user hits space
it pumps data about what happens when to an lsl stream
it also receive eeg data from a muse, or simulates it
This data is recorder along with events

EVENT KEY:
0 - Begin trial
1 - normal color displayed (blue)
2 - oddball color displayed (green)
3 - user pressed space
11 - end trial

It contains partially complete code to graph ERP afterwards.
The data is stored with tines normalized (timestamp 0 when stim first displayed, for each trial)
so setting up an ERP graph should be reasonably simple

Project ideas: any project where the user sees something displayed and interacts with it, while eeg is recorded

'''

import sys
import time
import csv
import random

from PyQt5 import QtGui
from PyQt5.QtOpenGL import *
from PyQt5 import QtCore, Qt
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPainter, QBrush, QPen, QPolygon
from pylsl import StreamInfo, StreamOutlet, local_clock, IRREGULAR_RATE
import numpy as np
from multiprocessing import Process, Queue
from utils.lsl_functions.pyqt5_send_receive import *
from utils.lsl_functions.muse_connect import send_muse
from utils.pyqt5_widgets import MplCanvas
from utils.lsl_functions.OpenBCI_connect_windows import send_openbci

SIMULATE = 0
FILE = 1
LIVESTREAM = 2

class oddball_win(QWidget):
    def __init__(self, hardware = None, model = None, sim_type = None, \
            data_type = None, csv_name = None, parent = None):
        super().__init__()

        self.parent = parent
        self.sim_type = sim_type
        self.hardware = hardware
        self.model = model
        timestamp = str(int(time.time()))
        self.csv_name = csv_name[:-4] + '_' + timestamp + ".csv"
        self.init_hardware_type()

        # MANUALLY SPECIFY COM PORT IF USING CYTON OR CYTON DAISY
        # if not specified, will use first available port
        # should be a string representing the COM port that the Cyton Dongle is connected to. 
        # e.g for Windows users 'COM3', for MacOS or Linux users '/dev/ttyUSB1
        self.com_port = None

        if data_type == 'Oddball live':
            self.data_type = LIVESTREAM
        elif data_type == 'Oddball simulate':
            self.data_type = SIMULATE
        else:
            raise Exception('Unknown data type: {} Try "Oddball live" or "Oddball simulate"'.format(data_type))


        self.setMinimumSize(600,600)
        self.setWindowIcon(QtGui.QIcon('utils/logo_icon.jpg'))
    
        # setting window title
        self.setWindowTitle('Oddball Window')
        
        # init layout
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        # self.layout.setContentsMargins(100,100,100,100)

        # this is a time elapsed variable - increments every time update runs
        global count
        count = 0
        self.count_timer = QtCore.QTimer()
        self.count_timer.timeout.connect(self.global_update)
        # self.count_timer.start(10)

        # defining what is oddball and what isn't
        # dict, values are tuples: color, stim code
        self.oddballs = {'normal' : (QtCore.Qt.blue, 1), 'oddball' : (QtCore.Qt.green, 2)}
        # whether to actually display a stimulus of specified color
        self.show_stim = False

        # setting up our lsl stream
        channels = 1
        srate = 100

        # setting up lsl stream for triggers
        self.trigger_info = StreamInfo('oddball triggers', 'EVENTS', channels, IRREGULAR_RATE, 'int16','myuid34234')
        self.trigger_outlet = StreamOutlet(self.trigger_info)

        # timers to send stimulus and trigger about it
        self.stim_start_timer = QtCore.QTimer()
        self.stim_start_timer.setSingleShot(True)
        self.stim_start_timer.timeout.connect(self.start_stim)
        # timer to end display of stimulus and send trigger of that
        self.stim_end_timer = QtCore.QTimer()
        self.stim_end_timer.setSingleShot(True)
        self.stim_end_timer.timeout.connect(self.end_stim)
        # timer to run between trials
        self.new_trial_timer = QtCore.QTimer()
        self.new_trial_timer.setSingleShot(True)
        self.new_trial_timer.timeout.connect(self.start_trial)

        self.is_stream_running = False
        self.streams_connected = False
        # here is a queue for checking whjhether streams are cinnected
        self.connected_q = Queue(10)

        # this is an emitter to tell us when the streams connect
        self.emitter = Emitter(self.connected_q)
        self.emitter.streams_connected.connect(self.handle_streams_connected)
        self.emitter.start()

        # let's start eeg receiving!
        self.start_data_stream()

        # now we can init stuff for our trials
        # trials is a list of random or addball in the order that we will use them (randomized, 20% oddball)
        self.total_trials = 10
        oddball_trials = self.total_trials // 5
        normal_trials = self.total_trials - oddball_trials
        self.trials = [self.oddballs['normal']]*normal_trials + [self.oddballs['oddball']]*oddball_trials
        random.shuffle(self.trials)
        print('trials {}'.format(self.trials))
        self.curr_trial = 0
        # this is whether or not we've gone through all our trials yet
        self.finished = False

        # now we display the instructions
        self.running_trial = False
        self.display_instructions()

    def init_hardware_type(self):
        # this function should run once, during __init__
        # let's set channels, sample rate, and expected data range based on hardware type

        print('init hardware is running with hardware',self.hardware,'model',self.model)
        if self.hardware == 'Muse':
            if self.model == 'Muse 2':
                self.srate = 250
                self.channels = 4
            elif self.model == 'Muse S':
                self.srate = 250
                self.channels = 4
        elif self.hardware == 'openBCI':
            if self.model == 'Ganglion':
                self.srate = 200
                self.channels = 4
            elif self.model == 'Cyton':
                print('using openbci cyton: REMEMBER TO MANUALLY SPECIFY COM PORT')
                self.srate = 250
                self.channels = 8
            elif self.model == 'Cyton-Daisy':
                print('using openbci cyton daisy: REMEMBER TO MANUALLY SPECIFY COM PORT')
                self.srate = 250
                self.channels = 16
        elif self.hardware == 'Blueberry':
            if self.model == 'Prototype':
                self.srate = 250
                self.channels = 4

        
    def handle_streams_connected(self):
        # runs when the streams_connected signal is received
        # makes it possible to start the trial
        print('window knows streams are connected')
        self.streams_connected = True


    def start_stim(self):
        # called by stim display start timer 
        # adds stim drawing to event loop, decides oddball or not
        # allows program to start collecting user responses
        print('starting stim')
        self.show_stim = True
        self.stim_end_timer.start(1000)
        self.trigger_outlet.push_sample([self.stim_code])
        self.update()
        
    def end_stim(self):   
        print('ending stim')
        self.show_stim = False
        self.trigger_outlet.push_sample([11])
        self.update()
        if not self.finished:
            self.new_trial_timer.start(1000)
        else:
            self.end_timer = QtCore.QTimer()
            self.end_timer.setSingleShot(True)
            self.end_timer.timeout.connect(self.on_end)
            self.end_timer.start(1000)
        
    def on_end(self):
        # called by end timer
        self.stop_data_stream()
        # let's initialize electrode to display
        self.curr_electrode = 0
        # and now start up erp graphing!
        
        # erp graphing is unused
        # self.display_erp()

        self.close()


    def display_instructions(self):
        # this will run at the beginning and needs a button press before anything else will happen

        self.label = QLabel()
        self.label.setFont(QtGui.QFont('Arial',14))
        self.label.setText('Look at the fixation cross.\nHit space when you see a green circle\nPress enter to begin')
        self.layout.addWidget(self.label)


    def start_trial(self):
        # starts trial - starts timers.
        print('starting trial')
        self.running_trial = True
        # setting current color and stim code based on value for current trial
        print(self.curr_trial)
        self.color = self.trials[self.curr_trial][0]
        self.stim_code = self.trials[self.curr_trial][1]
        self.stim_start_timer.start(500)
        self.trigger_outlet.push_sample([0])
        if self.curr_trial < self.total_trials - 1:
            self.curr_trial += 1
        else:
            print('all trials done')
            self.finished = True
            

    def start_data_stream(self):
        # this starts the stream for simulating or receiving from hardware
        # stream runs with pylsl (simulate or livestream)
        # either way, starts at least one new process which needs to be closed with stop_data_stream

        self.is_stream_running = True
        
        print('the stream data function is running in the pyqt5 window')
        
        if self.data_type == SIMULATE:
            if self.sim_type == 'Awake':
                self.sending_data = Process(target = sim_awake_eeg, args = (self.srate,self.channels,), name = 'sim data stream process', daemon = True)
            elif self.sim_type == 'Asleep':
                self.sending_data = Process(target = sim_asleep_eeg, args = (self.srate,self.channels,), name = 'sim data stream process', daemon = True)
            else:
                self.sending_data = Process(target = send_eeg, args = (self.srate,self.channels,True,), name = 'sim data stream process', daemon = True)
            self.sending_data.start()
            self.receiving_data = Process(target = receive_oddball, kwargs = {'csv_name':self.csv_name , 'q' : self.connected_q, 'channels' : self.channels}, name = 'receiving data process')
            self.receiving_data.start()
        elif self.data_type == LIVESTREAM:
            if self.hardware == 'Muse':
                self.sending_data = Process(target = send_muse, args = (250,4,), name = 'hardware data stream process', daemon = True)
                self.sending_data.start()
                self.receiving_data = Process(target = receive_oddball, kwargs = {'csv_name':self.csv_name , 'q' : self.connected_q, 'muse' : True, 'channels' : self.channels}, name = 'receiving data process')
                self.receiving_data.start()
            elif self.hardware == 'openBCI':
                if self.model == 'Ganglion':
                    print('Ganglion: user must start eeg stream from openbci gui')
                elif self.model == 'Cyton':
                    self.sending_data = Process(target = send_openbci, args = (self.channels,self.com_port), name = 'hardware data stream process', daemon = True)
                elif self.model == 'Cyton-Daisy':
                    self.sending_data = Process(target = send_openbci, args = (self.channels,self.com_port), name = 'hardware data stream process', daemon = True)
                    self.sending_data.start()
                self.receiving_data = Process(target = receive_oddball, kwargs = {'csv_name':self.csv_name , 'q' : self.connected_q, 'muse' : False, 'channels' : self.channels}, name = 'receiving data process')
                self.receiving_data.start()

        return

    def stop_data_stream(self, closing = False):
        # stop the stream process, turn off the timer
        # closing is whether or not this was called by closeEvent
        print('stop eeg stream ran')

        if self.is_stream_running:
            if self.data_type == SIMULATE or self.data_type == LIVESTREAM:
                self.sending_data.terminate()
                self.receiving_data.terminate()
                while self.sending_data.is_alive() or self.receiving_data.is_alive():
                    time.sleep(0.01)
                self.sending_data.close()
                self.receiving_data.close()
        self.is_stream_running = False

    def display_erp(self):
        # UNUSED

        # runs after all trials done
        # shows erp graph of the most recent finished trial
        # includes dropdown of which electrode to look at
        
        self.erp_layout = QVBoxLayout()
        self.erp_layout.setContentsMargins(100,100,100,100)
        self.layout.addLayout(self.erp_layout,0,0)

        self.erp_graph = MplCanvas(self, width=100, height=100, dpi=100)
        self.erp_layout.addWidget(self.erp_graph)
        self.dropdown = QComboBox()
        self.dropdown.addItems(['Electrode 1', 'Electrode 2','Electrode 3','Electrode 4'])
        self.dropdown.activated.connect(self.change_electrode)
        self.erp_layout.addWidget(self.dropdown)

        self.read_csv()

        self.graph_erp()
    
    def change_electrode(self):
        # runs when the user picks a new electrode from the dropdown
        self.curr_electrode = self.dropdown.currentIndex()
        self.graph_erp()
    
    def graph_erp(self):
        # this function actually graphs the erp of the current channel
        print('redrawing graph w e {}'.format(self.curr_electrode))
        self.erp_graph.axes.cla()
        self.erp_graph.axes.plot(self.data[self.curr_electrode])

    def read_csv(self):
        # this is unfinished
        # it's a space to write a function to read the csv, average the data, and display an erp graph

        pass


    
    def closeEvent(self, event):
        # this code will autorun just before the window closes
        # we will check whether streams are running, if they are we will close them
        print('close event works')
        if self.is_stream_running:
            # calling with True because we are closing
            self.stop_data_stream(closing = True)
        event.accept()

    def global_update(self):
        global count
        count += 1
        self.update()

    
    def triggered(self):
        # when user presses space this will run
        # sends smth to other lsl stream
        print('received user input')
        self.trigger_outlet.push_sample([3])
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Qt.Key_Space:
            print('received user input')
            self.trigger_outlet.push_sample([3])
        elif event.key() == Qt.Qt.Key_Return or event.key == Qt.Qt.Key_Enter:
            if self.streams_connected and not self.running_trial:
                self.start_trial()
                self.label.setVisible(False)

    def paintEvent(self, event):
        # here is where we draw stuff on the screen
        # you give drawing instructions in pixels - here I'm getting pixel values based on window size
        painter = QPainter(self)
        if self.show_stim:
            print('painting stim')
            painter.setBrush(QBrush(self.color, QtCore.Qt.SolidPattern))
            radius = self.geometry().width()//3
            painter.drawEllipse(radius, radius, radius, radius)
        elif self.running_trial and not self.finished:
            painter.setBrush(QBrush(QtCore.Qt.black, QtCore.Qt.SolidPattern))
            cross_width = 100
            line_width = 20
            center = self.geometry().width()//2
            painter.drawRect(center - line_width//2, center - cross_width//2, line_width, cross_width)
            painter.drawRect(center - cross_width//2, center - line_width//2, cross_width, line_width)
        elif self.finished:
            # no need to paint anything specifically
            pass


class Emitter(QtCore.QThread):
    """ 
    a thread to wait for the streams toconnect and send out a signal when they are
    after the signal is received, the window can start the trials
    """
    # this is a signal which will send a bool
    streams_connected = QtCore.pyqtSignal(bool)
    def __init__(self, q):
        super().__init__()
        print('emitter crceated')
        self.q = q     

    def run(self):
        # this will block until the queue contains smth then return the smth
        # if the thing is True, then the streams connected and we emit a signal
        if self.q.get():
            print('emitter looking in q')
            self.streams_connected.emit(True)
            
        

if __name__ == '__main__':    
    app = QApplication(sys.argv)    
    win = oddball_win() 
    win.show() 
    sys.exit(app.exec())