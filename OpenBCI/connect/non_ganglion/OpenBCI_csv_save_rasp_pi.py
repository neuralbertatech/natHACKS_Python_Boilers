'''
Authored by Eden Redman May 2021
For the use of validating Koalacademy (NeurAlbertaTech)
'''

# Import for EEG streaming
from pyOpenBCI import OpenBCICyton
import threading

# Import generic pacakges used throughout
import time
import numpy as np
import sys

# Import for exporting
import pandas as pd


debug = 0
count = 0

# Grab the Participant and Session number for experiment
if debug != 1:
    partnum = input("partnum: ") # enter participant in command prompt
    session_num = input("session_num: ")

# Initialize variables
SCALE_FACTOR = (4500000)/24/(2**23-1) #From the pyOpenBCI repo
start_time = time.time()
data =  np.array(np.zeros(17,dtype=float)) # timestamp (1), eeg data (16), colour data (3)
time_temp = np.zeros(1,dtype=float)
eeg_temp = np.zeros(16,dtype=float)
temp_concat = np.zeros(17,dtype=float)

if debug != 1:
    filename = "/home/pi/Koalacademy_Pi_Server/OpenBCI_save_test_{}_{}".format(partnum,session_num)
else:
    filename = "/home/pi/Koalacademy_Pi_Server/OpenBCI_save_test_{}_{}".format(1,1)

column_names = ["time","1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16"]

# Add the current sample to the larger data array (colour and EEG)
def save_data(temp_concat):
    global data
    global count
    data = np.vstack((data,np.array(temp_concat)))
    count += 1
    # print("test")

    if debug == 1:
        print(data)
        print(count)
        if count > 100:
            save_to_csv()
            print("finish")
            sys.exit()

    
# Callback from the serial stream function from pyOpenBCI - also grabs colour data
def collect_data(sample):
    # Get current time relative to the start of the experiment
    time_temp = np.array(start_time - time.time())
    # Get EEG values
    eeg_temp = [i*SCALE_FACTOR for i in sample.channels_data]

    # if debug == 1:
    #     print(time_temp)
    #     print(eeg_temp)
    #     print(colour_temp)

    # add to main temp array
    temp_concat[0] = time_temp
    temp_concat[1:17] = eeg_temp

    # call save functiona
    save_data(temp_concat)
    print(temp_concat)

def save_to_csv():
    global data
    data = pd.DataFrame(data=data, columns=column_names)
    data.to_csv(filename, float_format='%.3f', index=True)

board = OpenBCICyton(port='/dev/ttyUSB0', daisy=True)

if debug == 1:
    board.start_stream(collect_data)
    print("testy")
    time.sleep(3)

else:
    def start_cyton():
        try:
            board.start_stream(collect_data)
        except:
            pass

    def init_eeg():
        print("starting thread")
        y = threading.Thread(target=start_cyton)
        y.daemon = True
        y.start()

    if __name__ == '__main__':
        # call colour initialization function
        time.sleep(2)
        # start thread and call start_cyton which calls back to save_data
        init_eeg()

        time.sleep(100)
        board.disconnect()
save_to_csv()
board.disconnect()
