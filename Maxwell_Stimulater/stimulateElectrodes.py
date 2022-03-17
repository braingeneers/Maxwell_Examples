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
# 4. Prepare the stimulation helper functions
#
#    The stimulation units can be controlled through three independent
#    sources, what we call DAC channels (for digital analog converter).
#    By programming a DAC channel with digital values, we can control
#    the output the stimulation units. DAC inputs are in the range between
#    0 to 1023 bits, whereas 512 corresponds to zero volt and one bit
#    corresponds to 2.9 mV. Thus, to give a pulse of 100mV, the DAC
#    channel temporarily would need to be set to 512 + 34 (100mV/2.9)
#    and back again to 512.
#    To ensure that the stimulation sequence for each electrode/amplitude
#    pair is executed with correct timing, we chain all necessary commands
#    into a sequence data structure. The commands contained in a sequence are
#    executed immediately after each other.
#
# 5. Generate and use all electrode/amplitude stimulation pairs
#
#    We can now create an array containing all possible electrode/amplitude pairs
#    (with randomised order if needed) and then use it to stimulate the sample.
#    Immediately after every pulse, there is a time window of size
#    minimal_time_between_pulses (in ms) in which nothing happens and we also
#    let the system pause for 2 seconds between each electrode/amplitude stimulation pair.
#
# 6. Logging the stimulation sequence
#
#    Lastly, we save the used electrode/amplitude pair order into a npy file.
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
# Input the name the sequence log file should have
used_sequence_file_name = ''
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

# Input the number of pulses you want to send for each electrode/amplitude pair
nr_of_pulses = 5
# Input the time you want the system to do nothing after every stimulation pulse
inter_pulse_interval = 300  # in ms
# Input if you want to randomise the order of electrode/amplitude pairs used for stimulation
randomise = True



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

electrode_stim_unit_dict = {}
stimulation_units = []
working_stimulation_electrodes = []
corresponding_channels = []

for stim_el in stimulation_electrodes:
    array.connect_electrode_to_stimulation(stim_el)
    stim = array.query_stimulation_at_electrode(stim_el)
    if stim:
        electrode_stim_unit_dict[str(stim_el)] = stim
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
# 4. Prepare the stimulation helper functions
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


def create_sequence(stim_unit, amplitude, nr_of_pulses):
    stim = maxlab.chip.StimulationUnit(stim_unit)
    power_up = stim.power_up(True).connect(True).set_voltage_mode().dac_source(0)
    seq = maxlab.Sequence()
    seq.append(power_up)
    for i in range(nr_of_pulses):
        append_stimulation_pulse(seq, amplitude)
        seq.append(maxlab.system.DelaySamples(inter_pulse_interval * 20))
    power_down = maxlab.chip.StimulationUnit(stim_unit).power_up(False)   
    seq.append(power_down)  
    return seq


######################################################################
# 5. Generate and use all electrode/amplitude stimulation pairs
######################################################################

# First, poweroff all the stimulation units
for stimulation_unit in range(len(stimulation_units)):
    # Stimulation Unit
    stim = maxlab.chip.StimulationUnit(stimulation_unit)
    stim.power_up(False)
    stim.connect(False)
    maxlab.send(stim)

# We then create a array of shape [2, number_of_stimulation]
# which contains all possible stimulation electrode and amplitude pairs.
# If randomise is set to True, this array will then be shuffled, randomising
# the order in which the stimulations will occur. The shuffled array will
# later be stored and can be used to identify in which order the electrode/amplitude
# pairs were used to stimulate the sample.
stimulation_amplitudes = [int(np.round(i/2.9)) for i in range(min_amplitude, max_amplitude + 1, amplitude_steps)]
nr_of_amps = len(stimulation_amplitudes)
stim_number = nr_of_amps*len(stimulation_units)
used_sequence = np.zeros((3, stim_number))

for i, elec in enumerate(working_stimulation_electrodes):
    for j, amp in enumerate(stimulation_amplitudes):
        used_sequence[0, i * nr_of_amps + j] = elec
        used_sequence[1, i * nr_of_amps + j] = amp
        used_sequence[2, i * nr_of_amps + j] = corresponding_channels[i]

if randomise:
    ind = np.random.permutation(np.arange(stim_number))
    used_sequence = used_sequence[:, ind]

# Before we start the stimulation, we automatically start a recording which will be stored at the chosen location
s = maxlab.saving.Saving()
s.open_directory(data_path)
s.set_legacy_format(use_legacy_write)
s.group_delete_all()
if not record_only_spikes:
    s.group_define(0, "routed")
s.start_file(recording_file_name)
s.start_recording()
time.sleep(8)

# Iterate through all electrode/amplitude pairs:
# Power up one unit
# Deliver the pulse with the chosen amplitude
# Power down the unit
for i in range(stim_number):
    elec = used_sequence[0, i]
    amp = used_sequence[1, i]
    ch = used_sequence[2, i]
    stimulation_unit = electrode_stim_unit_dict[str(int(elec))]
    print('Next stimulation: Electrode {} on channel {} with an amplitude of {} mV using'
          ' stimulation unit {}'.format(int(elec), int(ch), 2.9*amp, stimulation_unit))
    seq = create_sequence(stimulation_unit, amp, nr_of_pulses)
    seq.send()
    time.sleep(int(nr_of_pulses * inter_pulse_interval / 1000 + 2))
    del seq
    time.sleep(2)

s.stop_recording()
s.stop_file()

######################################################################
# 6. Storing the used stimulation sequence
######################################################################
# The used sequence of electrode/amplitude pairs will be stored into a npy file
# and can be read using np.load(used_sequence_storage_path) 
np.save(data_path + '/' + used_sequence_file_name + '.npy', used_sequence)


