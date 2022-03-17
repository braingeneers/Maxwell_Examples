import zmq
import struct
from collections import namedtuple

SpikeEvent = namedtuple('SpikeEvent', 'frame channel amplitude')

if __name__ == '__main__':
    ctx = zmq.Context.instance()

    # Generate the subscriber sockets with the same settings as the
    # original C++ program.
    subscriber = ctx.socket(zmq.SUB)
    subscriber.setsockopt(zmq.RCVHWM, 0)
    subscriber.setsockopt(zmq.RCVBUF, 10*20000*1030)
    subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
    subscriber.setsockopt(zmq.RCVTIMEO, 100)
    subscriber.connect('tcp://localhost:7205')

    # Also generate a similar API socket.
    # api_socket = ctx.socket(zmq.REQ)
    # api_socket.setsockopt(zmq.RCVTIMEO, -1)
    # api_socket.connect('tcp://localhost:7210')

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

        events = []
        if events_data is not None:
            # The spike structure is 8 bytes of padding, a long frame
            # number, an integer channel (the amplifier, not the
            # electrode), and a float amplitude.
            spike_struct = '8xLif'
            spike_size = struct.calcsize(spike_struct)
            if len(events_data) % spike_size != 0:
                print(f'Events has {len(events_data)} bytes,',
                      f'not divisible by {spike_size}')
            # Iterate over consecutive slices of the raw events
            # data and unpack each one into a new struct.
            for i in range(0, len(events_data), spike_size):
                this_data = events_data[i:i+spike_size]
                ev = struct.unpack('8xLif', this_data)
                events.append(SpikeEvent(*ev))

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
