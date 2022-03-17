#!/usr/bin/python

import maxlab
import maxlab.system
import maxlab.chip
import maxlab.util
import maxlab.saving

import random
import time

## Setup script to prepare the configurations for the close-loop module
#
# 0. Initialize system
# 
# 1. Load a previously created configuration
# 
# 2. Connect two electrodes to stimulation units and power up stimulation units
# 
#    In rare cases it can happen that the selected electrode cannot be
#    stimulated. So, always check whether the electrode got properly
#    connected. As it is done in this example.  If the electrode is not
#    properly connected, the stimulation has no effect.
#
# 3. Prepare two different sequences of pulse trains
#
#    An almost infinite amount (only limited by the computer memory) of
#    independent stimulation pulse trains can be prepared without actually
#    deliver them yet.
#
# 4. Deliver the two pulse trains randomly
#
#    The previously prepared pulse trains can be delivered whenever
#    seems reasonable, or following a specific stimulation schedule.
# 


name_of_configuration = "/home/mxwbio/configs/211021/15h17m54s.cfg"
electrode1 = 12357
electrode2 = 22845
trigger_stimulation_amplitude = 6
close_loop_stimulation_amplitude = 10
data_directory = '/home/mxwbio/wetai/homepage/Projects/Maxwell_Controller/closed_loop_2/edited_code'

######################################################################
# 0. Initialize system
######################################################################

# The next two lines remove the two sequences, in case they were
# already defined in the server. We need to clear them here,
# otherwise the close_loop stimulation would also trigger, when
# we reconfigure the chip, due to the artifacts.
s = maxlab.Sequence('trigger', persistent=False)
del(s)
s = maxlab.Sequence('close_loop', persistent=False)
del(s)

# Normal initialization of the chip
maxlab.util.initialize()
maxlab.send(maxlab.chip.Core().enable_stimulation_power(True))
maxlab.send(maxlab.chip.Amplifier().set_gain(512))


# For the purpose of this example, we set the spike detection
# threshold a bit higher, to avoid/reduce false positives.
# Set detection threshold to 8.5x std of noise
maxlab.send_raw("stream_set_event_threshold  5") # previously was 8.5


######################################################################
# 1. Load a previously created configuration
######################################################################

array = maxlab.chip.Array('stimulation')
array.load_config( name_of_configuration )


######################################################################
# 2. Connect two electrodes to stimulation units
#    and power up the stimulation units
######################################################################

array.connect_electrode_to_stimulation( electrode1 )
array.connect_electrode_to_stimulation( electrode2 )

stimulation1 = array.query_stimulation_at_electrode( electrode1 )
stimulation2 = array.query_stimulation_at_electrode( electrode2 )

if not stimulation1:
    print("Error: electrode: " + str(electrode1) + " cannot be stimulated")

if not stimulation2:
    print("Error: electrode: " + str(electrode2) + " cannot be stimulated")

# Download the prepared array configuration to the chip
array.download()
maxlab.util.offset()


# Prepare commands to power up and power down the two stimulation units
cmd_power_stim1 = maxlab.chip.StimulationUnit(stimulation1).power_up(True).connect(True).set_voltage_mode().dac_source(0)
cmd_power_down_stim1 = maxlab.chip.StimulationUnit(stimulation1).power_up(False)
cmd_power_stim2 = maxlab.chip.StimulationUnit(stimulation2).power_up(True).connect(True).set_voltage_mode().dac_source(0)
cmd_power_down_stim2 = maxlab.chip.StimulationUnit(stimulation2).power_up(False)


# Use the electrode next to the stimulation electrode for trigger detection
amp = array.query_amplifier_at_electrode( electrode1+1 )
print("This amplifier channel is connected to the electrode next to the first stimulation electrode: " + amp)
print("Use this channel to detect (simulated) spikes in the C++ close cloop application")



######################################################################
# 3. Prepare two different sequences of pulse trains
######################################################################

def append_stimulation_pulse(seq, amplitude):
    seq.append( maxlab.chip.DAC(0, 512-amplitude) )
    seq.append( maxlab.system.DelaySamples(4) )
    seq.append( maxlab.chip.DAC(0, 512+amplitude) )
    seq.append( maxlab.system.DelaySamples(4) )
    seq.append( maxlab.chip.DAC(0, 512) )
    return seq


# Prepare one pulse called 'trigger', we use this to simulate a spike
# on one of the channels by applying an electrical stimulation pulse
sequence1 = maxlab.Sequence('trigger', persistent=True)
sequence1.append( cmd_power_stim1 )
append_stimulation_pulse(sequence1, trigger_stimulation_amplitude)
sequence1.append( cmd_power_down_stim1 )


# Create another pulse called 'close_loop' to stimulate the second electrode.
# This sequence needs to be prepared here in python, but it will be triggered
# through the 'close_loop' token in the C++ application
sequence2 = maxlab.Sequence('close_loop', persistent=True)
sequence2.append( cmd_power_stim2 )
append_stimulation_pulse(sequence2, close_loop_stimulation_amplitude)
sequence2.append( cmd_power_down_stim2 )


######################################################################
# Deliver 200 stimulation pulses to the trigger electrode
######################################################################

print("Start delivering stimulation pulses to the trigger electrode")

wells = range(1)  
use_legacy_write = True
record_only_spikes = False
recording_file_name = "UCSF_Pilot_Drugs"

#s = maxlab.saving.Saving()
#s.open_directory(data_directory)

#s.set_legacy_format(True) # Using legacy format

#s.start_file("testit")

#print("Start saving to file")
#s.start("close_loop_test")
#time.sleep(1)
#for rep in range(20):  # Get results faster by making range small
#    sequence1.send()
#    print("helo")
#    time.sleep(0.5)

#print("Stop saving to file")
#s.stop()

# Copied saving code from more up to date python api
s = maxlab.saving.Saving()
s.open_directory(data_directory)
s.set_legacy_format(use_legacy_write)
s.group_delete_all()
if not record_only_spikes:
    for well in wells:
        s.group_define(well, "routed")
s.start_file(recording_file_name)
s.start_recording(wells)

# Record for 60 seconds, then stop and save.
#for i in range(6):
#    time.sleep(10)
#    print((i+1)*10)

#s.start("close_loop_test")
for rep in range(60):  # Get results faster by making range small
    sequence1.send()
    print(rep)
    time.sleep(0.5)


s.stop_recording()
s.stop_file()
s.group_delete_all()







