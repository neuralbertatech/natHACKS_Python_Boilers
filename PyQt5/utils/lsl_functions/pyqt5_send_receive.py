'''
various functions to send and recive lsl streams and interact with queues
They simulate data, read files, receive data, etc
Receive blank is easily customizable, and the basic template of others can slos be customized
'''

import sys
from math import sqrt, acos, pi, sin

from pylsl import StreamInlet, resolve_byprop, resolve_stream, local_clock
from multiprocessing import Process, Queue,set_start_method
from pylsl import StreamInfo, StreamOutlet
import numpy as np
import random
import time
import csv


import pdb

            
def send_eeg(srate = 250, channels = 4, sine = False):
    # this function fakes eeg data - neither awake or asleep, just sine waves
    # this is the function called in the process strated by simulate_data
    # srate is sample rate in Hz, times per secodn to send out data
    print('gs start with srate',srate,'channels',channels,'sine',sine)
    # what exactly do all these things mean? Do they matter?
    wait = 1/srate
    eeg_info = StreamInfo('BioSemi - address','EEG',channels,srate,'float32','myuid34234')
    
    eeg_outlet = StreamOutlet(eeg_info)
    
    # I guess a while true loop is necessary
    # for debugging we will only send 3 data points
    i = 0
    while True:
        if sine:
            if channels == 4:
                # only works for 4 channel setup
                samples = np.array([1000*sin(time.time()*6)] + [200*sin(time.time()*3)] + [100*sin((time.time()+2)*6)] + [800*sin((time.time()+1)*3)])
            else:
                samples = np.array([1000*sin(time.time()*6)]*4)
        else:
            samples = np.random.randint(0,101,channels)
        eeg_outlet.push_sample(samples)
        # print(' gs pushed '+str(samples)+'\n')
        time.sleep(wait)

def sim_awake_eeg(srate = 250, channels = 4):
    # this function fakes eeg data - sends to lsl stream
    # it's copied from the software workshop with various edits
    info = StreamInfo('BioSemi', 'EEG', channels, srate, 'float32', 'myuid34234')
    # next make an outlet
    outlet = StreamOutlet(info)
    # a list of 250 values from 0 to 250 separated by 2pi 
    x = np.linspace(0, 2*np.pi, 250)

    focused = (1,5)
    unfocused = (5,1)
    
    alpha_amp,beta_amp = focused
    attention = True

    count = 0
    while True:
        # change focus every 10 seconds
        if count%(250*10) == 0:
            if attention:
                alpha_amp,beta_amp = unfocused
                attention = False
            else:
                alpha_amp,beta_amp = focused
                attention = True
           

        tstep = x[count%250] # value used to make the waves

        sample = np.zeros(channels)
        for i in range(len(sample)):
            sample[i] = wave_maker(tstep, 9, alpha_amp * 1.5, 20) + wave_maker(tstep, 17, beta_amp, 20)
        
        outlet.push_sample(sample)

        count+=1

        time.sleep(1/srate)

def sim_asleep_eeg(srate = 250, channels = 4):
    # this function fakes eeg data - sends to lsl stream
    # it's copied from the software workshop with various edits
    info = StreamInfo('BioSemi', 'EEG', channels, srate, 'float32', 'myuid34234')
    # next make an outlet
    outlet = StreamOutlet(info)
    # a list of 250 values from 0 to 250 separated by 2pi 
    x = np.linspace(0, 2*np.pi, 250)

    slow = (1,5)
    less_slow = (5,1)
    
    alpha_amp,beta_amp = slow
    attention = True

    count = 0
    while True:
        # change focus every 10 seconds
        if count%(250*10) == 0:
            if attention:
                delta_amp,theta_amp = less_slow
                attention = False
            else:
                delta_amp,theta_amp = slow
                attention = True
           

        tstep = x[count%250] # value used to make the waves

        sample = np.zeros(channels)
        for i in range(len(sample)):
            sample[i] = wave_maker(tstep, 2, alpha_amp * 1.5, 20) + wave_maker(tstep, 7, beta_amp, 20)
        
        outlet.push_sample(sample)

        count+=1

        time.sleep(1/srate)

def receive_eeg(gq, strip_times = False, data_type = 'EEG', channels = 4):
        # receives a single eeg stream and queues it
        print('gr start\n')
        streams = resolve_byprop('type','EEG')
        print('gr found streams '+str(streams)+'\n')
        eeg_inlet = StreamInlet(streams[0])
        print('gr found EEG inlet '+str(eeg_inlet)+'\n')
        
        while True:
            sample, timestamp = eeg_inlet.pull_sample()
            # print('r list {} point {}'.format(type(sample),sample))
            # print('r list',type(sample),'point',sample)
            if strip_times:
                gq.put(sample[:channels])
            else:
                gq.put((sample,timestamp))

def read_file(fname,hardware,model,q, srate = 250, channels = 4):
    # will be run if user decided to run from a file
    # fname is the file name with appropriate path (csv file)
    # pumps data into the queue (q) at desired framerate (set using the time.sleep)
    print('rf start file {} hardware {} model {} srate {}'.format(fname, hardware, model, srate))
    wait = 1/srate
    with open(fname, mode = 'r') as file:
        csv_reader = csv.reader(file, delimiter=',', quoting = csv.QUOTE_NONNUMERIC)
        line_count = 0
        for row in csv_reader:
            if line_count <= 1:
                line_count += 1
                continue
            # only take first [channels] numbers to exclude 0 column and time
            sample = row[:channels]
            # print('fr read {}'.format(sample))
            q.put(sample)
            line_count += 1
            time.sleep(wait)

def receive_blank(csv_name = 'blank_receive_log.csv'):
    streams = resolve_byprop('type','EEG')
    print('blank r found streams '+str(streams)+'\n')
    eeg_inlet = StreamInlet(streams[0])
    print('blank r found EEG inlet '+str(eeg_inlet)+'\n')
    start_time = time.time()
    # we call the time correction before we start the loop because the first call takes some time and subsequent ones are fast
    correction = eeg_inlet.time_correction()
    print('r time correction {}'.format(correction))
    while True:
        correction = eeg_inlet.time_correction()
        # if time.time() - start_time > 10:
        #     break
        sample, timestamp = eeg_inlet.pull_sample()
        timestamp += correction
        print('gr',timestamp,sample)
        # print('r list {} point {}'.format(type(sample),sample))
        print('r point',sample)
        with open(csv_name, mode='a',newline = '') as file:
                fwriter = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                fwriter.writerow([timestamp,sample])

def receive_oddball(csv_name = 'oddball_receive_log.csv', q = None, muse = False):
    # receives data from 2 streams and records them both in csv file
    # one stream is type eeg, other stream is type events, menat to have triggers during oddboll task
    # when it has successfully conncetd to the streams, sends True to the queue
    streams = resolve_byprop('type','EEG')
    print('ro found streams '+str(streams)+'\n')
    eeg_inlet = StreamInlet(streams[0])
    print('ro found EEG inlet '+str(eeg_inlet)+'\n')
    streams = resolve_byprop('type','EVENTS')
    trigger_inlet = StreamInlet(streams[0])
    print('ro found trigger inlet '+str(trigger_inlet)+'\n')
    start_time = time.time()
    # we call the time correction before we start the loop because the first call takes some time and subsequent ones are fast
    eeg_correction = eeg_inlet.time_correction()
    trigger_correction = trigger_inlet.time_correction()
    print('ro time correction eeg {}, trigger {}'.format(eeg_correction, trigger_correction))
    q.put(True)
    # this will get set properly later
    trial_time = 0

    # this is to convert times (muse always uses epoch time, not local_clock)
    epoch_to_local_diff = time.time() - local_clock()

    # we won't save the data from before th first trial starts, so set to False
    saving_data = False
    while True:
        eeg_correction = eeg_inlet.time_correction()
        trigger_correction = trigger_inlet.time_correction()
        # if time.time() - start_time > 10:
        #     break
        eeg_sample, eeg_timestamp = eeg_inlet.pull_sample()
        # print(eeg_sample)
        if muse:
            # muse always uses epoch, not local clock, so must convert
            eeg_timestamp -= epoch_to_local_diff
        eeg_timestamp += eeg_correction
        eeg_timestamp -= trial_time
        eeg_sample = eeg_sample[:4]
        # print('gr',eeg_timestamp,eeg_sample)
        # since there usually won't be a sample from the trigger stream, we pull with no wait time
        trigger_sample, trigger_timestamp = trigger_inlet.pull_sample(0.0)
        with open(csv_name, mode='a',newline = '') as file:
                fwriter = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                if trigger_sample != None:
                    if trigger_sample == [0]:
                        # a new trial has started! Let's normalize times to be 0 now
                        # print('trigger_sample', trigger_sample, 'trigger_timestamp', trigger_timestamp, 
                        #     'trigger_correction', trigger_correction, 'eeg_sample', eeg_sample, 
                        #     'eeg_timestamp', eeg_timestamp, 'eeg_correction', eeg_correction)
                        # print('epoch_to_local_diff', epoch_to_local_diff)  
                        # print('eeg_timestamp', eeg_timestamp)      
                        trial_time = trigger_timestamp
                        saving_data = True   
                    trigger_timestamp += trigger_correction
                    trigger_timestamp -= trial_time
                    fwriter.writerow([eeg_timestamp] + eeg_sample + [trigger_timestamp] + trigger_sample)
                elif saving_data == True:
                    # this will fail if the first trial has not yet started, so we won't save data from before that
                    fwriter.writerow([eeg_timestamp] + eeg_sample)


def wave_maker(angle, freq, amp, noise):
    '''
    This allows the creation of sine waves for simulating data
    angle should be kept track of in the function calling wave maker
    '''
    return(amp * sin(angle * freq) + random.uniform(-noise, noise))
   


if __name__ == '__main__':
    # testing oddball and others
    receive_blank()
