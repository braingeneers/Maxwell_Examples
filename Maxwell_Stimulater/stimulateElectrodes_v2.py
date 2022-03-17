#!/usr/bin/python

import maxlab
import maxlab.system
import maxlab.chip
import maxlab.util
import maxlab.saving

import time
import numpy as np


## Stimulation script to stimulate with multiple electrodes and amplitudes
#
# 0. Initialize system into a defined state
#
#    It is best to initialize the system into a defined state before
#    Starting any script. This way, one can be sure that the system
#    is always in the same state while running the script, regardless
#    of what has been done before with it.
#
#    In this step, we also issue the following command:
#
#       maxlab.send(maxlab.chip.Core().enable_stimulation_power(True))
#
#    This is needed, because by default the stimulation units are
#    powered off globally...
#
# 1. Load your electrode selection
#
#    We use the existing config file to route the electrodes of interest.
#
# 2. Connect stimulation units to the stimulation electrodes.
#
#    Once an array configuration has been obtained, the stimulation units
#    can be connected to the desired electrodes.
#    With this step, one needs to be careful, in rare cases it can happen
#    that an electrode cannot be stimulated. For example, the electrode
#    could not be routed (due to routing constraints).
#
# 3. Power up and configure the stimulation units
#
#    Once the electrodes are connected to the stimulation units (this was
#    done in the step above), the stimulation units need to be configured
#    and powered up.
#
# 4. Apply the same pulses to all selected stimulation units at the same time
#
#    The stimulation units can be controlled through three independent
#    sources, what we call DAC channels (for digital analog converter).
#    By programming a DAC channel with digital values, we can control
#    the output the stimulation units. DAC inputs are in the range between
#    0 to 1023 bits, whereas 512 corresponds to zero volt and one bit
#    corresponds to 2.9 mV. Thus, to give a pulse of 100mV, the DAC
#    channel temporarily would need to be set to 512 + 34 (100mV/2.9)
#    and back again to 512.
#    In this example, all stimulation units are controlled through the same DAC
#    channel ( dac_source(0) ), thus by programming a buphasic pulse
#    on DAC channel 0, all the stimulation units exhibit the biphasic
#    pulse.
#
#
#

######################################################################
# User Input
######################################################################

# Input the path to the config file you want to use
name_of_configuration = ''
# Input the path of the directory where the recording and sequence log should be stored
data_path = ''
# Input the name the recording file should have
recording_file_name = ''
# Input your choice of data format (True for legacy format)
use_legacy_write = False
# Input wheter you want to record spikes only, or signals as well
record_only_spikes = False


# For now no more than 32 electrodes can be selected for stimulation and they
# already need to be routed through the config file

# Input which electrodes you want to use for stimulation (subset of recording electrodes)
stimulation_electrodes = []
# Input the minimal stimulation voltage to be used
min_amplitude = 100  # in mV
# Input the maximal stimulation voltage to be used
max_amplitude = 250  # in mV
# Input the step size for the different stimulation voltages
amplitude_steps = 50  # in mV

# The amplitude array will then be generated using the command
# [int(np.round(i/2.9)) for i in range(min_amplitude, max_amplitude + 1, amplitude_steps)]
# E.g. with the currently set values this will give you the amplitude array
# [34, 52, 69, 86] which will then stimulate the electrode with the amplitudes
# [98.6, 150.8, 200.1, 249.4]

# Input the number of stimulations you want to do for each amplitude
nr_stims_per_amp = 5
# Input the number of pulses you want to send for each stimulation cycle
nr_of_pulses = 5
# Input the time you want the system to do nothing after every stimulation pulse
inter_pulse_interval = 300  # in ms
# Input the time you want the system to do nothing after every stimulation burst
inter_burst_interval = 2000  # in ms




# 0. Initialize system into a defined state
maxlab.util.initialize()
maxlab.send(maxlab.chip.Core().enable_stimulation_power(True))



######################################################################
# 1. Load your electrode selection
######################################################################
# Enter the path to your configuration file of choice
array = maxlab.chip.Array('stimulation')
array.load_config(name_of_configuration)



######################################################################
# 2. Connect stimulation units to the stimulation electrodes.
######################################################################

stimulation_units = []
working_stimulation_electrodes = []
corresponding_channels = []

for stim_el in stimulation_electrodes:
    array.connect_electrode_to_stimulation(stim_el)
    stim = array.query_stimulation_at_electrode(stim_el)
    if stim:
        stimulation_units.append(stim)
        working_stimulation_electrodes.append(stim_el)
        ch = array.query_amplifier_at_electrode(stim_el)
        corresponding_channels.append(ch)
    else:
        print("No stimulation channel can connect to electrode: " + str(stim_el))

# Download the prepared array configuration to the chip
array.download()
maxlab.util.offset()

print('Electrode / Channel pairs to be used for stimulation:')
for i in range(len(working_stimulation_electrodes)):
    print('Elec: {} - Channel: {}'.format(working_stimulation_electrodes[i], corresponding_channels[i]))

######################################################################
# 3. Power up and configure the stimulation units
######################################################################

stimulation_unit_commands = []

for stimulation_unit in stimulation_units:
    # Stimulation Unit
    stim = maxlab.chip.StimulationUnit(stimulation_unit)
    stim.power_up(True)
    stim.connect(True)
    stim.set_voltage_mode()
    stim.dac_source(0)
    stimulation_unit_commands.append(stim)
    maxlab.send(stim)


######################################################################
# 4. Apply the same pulses to all selected stimulation units at the same time
######################################################################

# Create a stimulation pulse
# When the stimulation buffers are set to voltage mode, they act like
# an inverting amplifier. Thus here we need to program a negative first
# biphasic pulse, to get a positive first pulse on the chip.
def append_stimulation_pulse(seq, amplitude):
    amplitude = int(amplitude)
    seq.append(maxlab.chip.DAC(0, 512-amplitude))
    seq.append(maxlab.system.DelaySamples(4))
    seq.append(maxlab.chip.DAC(0, 512+amplitude))
    seq.append(maxlab.system.DelaySamples(4))
    seq.append(maxlab.chip.DAC(0, 512))
    return seq


# we generate the amplitude vector containing all amplitudes we will stimulate with sequentially on all electrodes)
stimulation_amplitudes = [int(np.round(i/2.9)) for i in range(min_amplitude, max_amplitude + 1, amplitude_steps)]
nr_of_amps = len(stimulation_amplitudes)

# Before we start the stimulation, we automatically start a recording which will be stored at the chosen location
s = maxlab.saving.Saving()
s.open_directory(data_path)
s.set_legacy_format(use_legacy_write)
s.group_delete_all()
if not record_only_spikes:
    s.group_define(0, "routed")
s.start_file(recording_file_name)
s.start_recording()
time.sleep(2)

for amp in stimulation_amplitudes:
    seq = maxlab.Sequence()
    for rep in range(nr_stims_per_amp):
        for pulse in range(nr_of_pulses):
            append_stimulation_pulse(seq, amp)
            seq.append(maxlab.system.DelaySamples(inter_pulse_interval * 20))
        seq.append(maxlab.system.DelaySamples(inter_burst_interval * 20))

    print('Stimulating with an amplitude {}MV'.format(amp * 2.9))
    seq.send()
    time.sleep(nr_of_pulses * (inter_pulse_interval/1000) + nr_stims_per_amp * (inter_burst_interval/1000))

s.stop_recording()
s.stop_file()















