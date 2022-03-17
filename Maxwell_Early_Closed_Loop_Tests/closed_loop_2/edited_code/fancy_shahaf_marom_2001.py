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
# 1. Initialize system and load previously created configuration
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



######################################################################
# CONFIGURATION PARAMETERS
######################################################################
minutes = 60
baseline_time_sec = 5*minutes
stimulation_time_sec = 10*minutes

name_of_configuration = "closeLoop.cfg"
electrode1 = 13248
electrode2 = 13378
trigger_stimulation_amplitude = 6
close_loop_stimulation_amplitude = 10
data_directory = "."



######################################################################
# UTILITY FUNCTIONS
######################################################################

def StimulationUnit(elec):
    "Create a StimulationUnit object for the given electrode."
    array.connect_electrode_to_stimulation(elec)
    stim = array.query_stimulation_at_electrode(elec)

    if not stim:
        raise ValueError(f'Electrode {elec} cannot be stimulated.')

    return maxlab.chip.StimulationUnit(stim)


def StimSequence(name, stim_unit, amplitude):
    "Create a Sequence for a positive-negative stim pulse."
    seq = maxlab.Sequence(name, persistent=True)
    seq.append(
            stim_unit.power_up(True).connect(True)
            .set_voltage_mode().dac_source(0))
    seq.append(maxlab.chip.DAC(0, 512-amplitude))
    seq.append(maxlab.system.DelaySamples(4))
    seq.append(maxlab.chip.DAC(0, 512+amplitude))
    seq.append(maxlab.system.DelaySamples(4))
    seq.append(maxlab.chip.DAC(0, 512))
    seq.append(stim_unit.power_up(False))
    return seq



######################################################################
# INITIALIZE SYSTEM
######################################################################

# Remove any previously defined sequences so they don't get accidentally
# triggered when the chip is configured.
for seq in 'trigger', 'close_loop':
    maxlab.Sequence(seq).shutdown()

# Normal initialization of the chip, except the stream event threshold is
# ridiculous because we're not actually looking for spiking events and stim
# events are enormous.
maxlab.util.initialize()
maxlab.send(maxlab.chip.Core().enable_stimulation_power(True))
maxlab.send(maxlab.chip.Amplifier().set_gain(512))
maxlab.send_raw("stream_set_event_threshold  8.5")

# Load the configuration that shipped with this example. You can also construct
# these configurations manually using the API, which is going to be the right
# answer moving forwards.
array = maxlab.chip.Array('stimulation')
array.load_config( name_of_configuration )

# Connect two electrodes to stimulation units.
stim1 = StimulationUnit(electrode1)
stim2 = StimulationUnit(electrode2)

# Download the prepared array configuration to the chip
array.download()
maxlab.util.offset()

# Use the electrode next to the stimulation electrode for trigger detection
amp = array.query_amplifier_at_electrode( electrode1+1 )
print("This amplifier channel is connected to the electrode next to the first stimulation electrode: " + amp)
print("Use this channel to detect (simulated) spikes in the C++ close cloop application")


######################################################################
# DELIVER STIMULATION PROTOCOL
######################################################################

s = maxlab.saving.Saving()
s.open_directory(data_directory)
s.start("close_loop_test")

print('Beginning baseline phase.')
time.sleep(baseline_time_sec)

print('Beginning stimulation phase.')
last_time = time.time()
for rep in range(stimulation_time_sec * 10):

    # Stimulate each separate electrode.

    time.sleep(0.1 + last_time - time.time())
    last_time += 0.1

print('Finished protocol, saving to file.')
s.stop()
