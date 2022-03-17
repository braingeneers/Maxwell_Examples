import time 

import maxlab
import maxlab.chip
import maxlab.util


maxlab.util.initialize()

# Configure array
a = maxlab.chip.Array()
a.connect_amplifier_to_stimulation(100)
stim_unit = a.query_stimulation_at_amplifier(100)
a.download()

# Configure amplifier and core
maxlab.send(maxlab.chip.Core().enable_stimulation_power(1))
maxlab.send(maxlab.chip.Amplifier(1))

# Configure stimulation unit
maxlab.send(maxlab.chip.StimulationUnit(stim_unit).power_up(1).connect(1).dac_source(0))

time.sleep(4)

# Do recording if needed
#save = maxlab.saving.Saving()
#save.start_file("file")
#save.start_recording()

for i in range(1000):
    maxlab.send(maxlab.chip.DAC(0,1000))
    time.sleep(0.5)

#save.stop_recording()
#save.stop_file()

