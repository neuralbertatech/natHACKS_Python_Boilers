from pyOpenBCI import OpenBCICyton
from pylsl import StreamInfo, StreamOutlet
import numpy as np

SCALE_FACTOR_EEG = (4500000)/24/(2**23-1) #uV/count
SCALE_FACTOR_AUX = 0.002 / (2**4)

def send_openbci(channels, com = None):
    '''
    This function connectsto openbci cyton or cyton daisy and send approp lsl stream
    channels needs to be 8 (cyton) or 16 (with daisy)
    com: the com port to use. If none is given, will use first available
    Should be 'A string representing the COM port that the Cyton Dongle is connected to. 
    e.g for Windows users 'COM3', for MacOS or Linux users '/dev/ttyUSB1'.'
    '''
    if channels == 8:
        daisy = False
    elif channels == 16:
        daisy = True
    else:
        raise Exception('Channels must be 8 (cyton) or 16 (cyton with daisy')
    
    print('\nConnecting to openbci: com port {} daisy {}'.format(com, daisy))
    print("Creating LSL stream for EEG. \nName: OpenBCIEEG\nID: OpenBCItestEEG\n")

    info_eeg = StreamInfo('OpenBCIEEG', 'EEG', channels, 250, 'float32', 'OpenBCItestEEG')

    print("Creating LSL stream for AUX. \nName: OpenBCIAUX\nID: OpenBCItestEEG\n")

    info_aux = StreamInfo('OpenBCIAUX', 'AUX', 3, 250, 'float32', 'OpenBCItestAUX')

    outlet_eeg = StreamOutlet(info_eeg)
    outlet_aux = StreamOutlet(info_aux)

    def lsl_streamers(sample):
        # callback function called by board
        outlet_eeg.push_sample(np.array(sample.channels_data)*SCALE_FACTOR_EEG)
        outlet_aux.push_sample(np.array(sample.aux_data)*SCALE_FACTOR_AUX)
  
    if com:
        board = OpenBCICyton(port=com, daisy = daisy) # need to put in the COM port that the OpenBCI dongle is attached to
    else:
        board = OpenBCICyton(daisy = daisy)

    board.start_stream(lsl_streamers)

