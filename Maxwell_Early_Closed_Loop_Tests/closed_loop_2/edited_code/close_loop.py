import sys
import zmq
import struct
import array
from collections import namedtuple


SpikeEvent = namedtuple('SpikeEvent', 'frame channel amplitude')


def send_command(api_socket, string):
    '''
    Send a MaxWell API command to a ZMQ socket, check that the reply is
    "OK", and if not, print the error that occurred.
    '''
    api_socket.send_string(string)
    reply = api_socket.recv_string()
    if reply != 'OK':
        print(f'An error occurred {reply}.')
        api_socket.send_string('get_errors')
        print(api_socket.recv_string())

 
if __name__ == '__main__':
    ctx = zmq.Context.instance()

    # Provide an argument to do closed loop on that channel, otherwise
    # don't do any stim but print spikes as they happen.
    receive_channel = -1 if len(sys.argv) < 2 else int(sys.argv[1])

    # Generate the subscriber sockets with the same settings as the
    # original C++ program.
    subscriber = ctx.socket(zmq.SUB)
    subscriber.setsockopt(zmq.RCVHWM, 0)
    subscriber.setsockopt(zmq.RCVBUF, 10*20000*1030)
    subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
    subscriber.setsockopt(zmq.RCVTIMEO, 100)
    subscriber.connect('tcp://localhost:7205')

    # Also generate a similar API socket.
    api_socket = ctx.socket(zmq.REQ)
    api_socket.setsockopt(zmq.RCVTIMEO, -1)
    api_socket.connect('tcp://localhost:7210')

    # This first loop ignores any partial packets to make sure the real
    # loop gets aligned to an actual frame. First it spins for as long
    # as recv() fails, then it waits for the RCVMORE flag to be False to
    # check that the last partial frame is over.
    more = True
    while more:
        try:
            msg = subscriber.recv()
        except zmq.ZMQError as e:
            continue
        more = subscriber.getsockopt(zmq.RCVMORE)

    while True:
        # Sometimes the publisher will be interrupted, so don't let that
        # crash the entire program, just skip the frame.
        frame_number = frame_data = events_data = None
        try:
            # The first component of each message is the frame number as
            # a long long, so unpack that.
            frame_number = struct.unpack('Q', subscriber.recv())[0]

            # We're still ignoring the frame data, but we have to get it
            # out from the data stream in order to skip it.
            if subscriber.getsockopt(zmq.RCVMORE):
                frame_data = subscriber.recv()

            # This is the one that stores all the spikes.
            if subscriber.getsockopt(zmq.RCVMORE):
                events_data = subscriber.recv()

        except Exception as e:
            print(e)
            continue

        # `frame_data` is a 1027-element array containing the recorded voltage
        # at each electrode, so unpack that into a usable format.
        frame = array.array('f', frame_data)

        events = []
        if events_data is not None:
            # The spike structure is 8 bytes of padding, a long frame
            # number, an integer channel (the amplifier, not the
            # electrode), and a float amplitude.
            spike_struct = '8xLif'
            spike_size = struct.calcsize(spike_struct)
            if len(events_data) % spike_size != 0:
                print(f'Events has {len(events_data)} bytes,',
                      f'not divisible by {spike_size}', file=sys.stderr)

            # Iterate over consecutive slices of the raw events
            # data and unpack each one into a new struct.
            for i in range(0, len(events_data), spike_size):
                ev = SpikeEvent(*struct.unpack(spike_struct,
                    events_data[i:i+spike_size]))
                events.append(ev)

                # If the event is on the channel of interest, tell the
                # server to send the stimulation pattern that gets
                # defined by the provided Python script.
                if ev.channel == receive_channel:
                    print(f'Event detected on {receive_channel}. Sending stim command...')
                    send_command(api_socket, 'sequence_send close_loop')


        # Just dump them to the console to show it works.
        if len(events) > 0:
            print(events)

    # If you split this code into multiple threads, e.g. to consolidate
    # this script with the one that handles the recordings, it will be
    # necessary to delete each subscriber to the ZMQ context separately
    # using the usual Python operator `del`, and then terminate the
    # context with `ctx.term()`. In a single-threaded script like this,
    # though, it's fine to just let the Python interpreter run all these
    # destructors when the program terminates.
