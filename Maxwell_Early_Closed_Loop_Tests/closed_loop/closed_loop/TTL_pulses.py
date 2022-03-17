import maxlab
import maxlab.system

# Program the direction of the GPIO pins to output
# this needs to be done once per "session", i.e. power up of MaxOne.
direction = maxlab.system.GPIODirection(0xFF)
maxlab.send(direction)


# Output a '1' to all 8 GPIOs pins for one second
maxlab.send(maxlab.system.GPIOOutput(0b11111111))
time.sleep(1)
maxlab.send(maxlab.system.GPIOOutput(0b00000000))


# Toggle the GPIOs in a controlled manner
def append_toggle_GPIOs(seq, bits):
    seq.append( maxlab.system.GPIOOutput(bits) )
    seq.append( maxlab.system.DelaySamples(100) ) # delay for 100 samples (5 ms)
    seq.append( maxlab.system.GPIOOutput(0) )
    return seq


sequence = maxlab.Sequence('ttl', persistent=True)
append_toggle_GPIOs(sequence, 0xFF)



# Send the TTL sequence:
sequence.send()

# Send the TT sequence again
sequence.send()

