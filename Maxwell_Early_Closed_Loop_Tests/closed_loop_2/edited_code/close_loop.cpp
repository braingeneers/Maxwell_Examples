#include <vector>
#include <iostream>
#include <zmq.hpp>


struct SpikeEvent
{
    unsigned long filler = 0; // Added by me to try to make the representation make sense...
    unsigned long frameNo;    //!< Frame number (time point) at which spike is detected.
    int channel;              //!< Channel number at which spike is detected.
    float amp;                //!< Amplitude of a detected spike.

    SpikeEvent(unsigned long f, int c, float a)
        :frameNo(f),
        channel(c),
        amp(a)
    { }

    static const unsigned int bSize = 2*sizeof(unsigned long) +
                                      sizeof(int) +
                                      sizeof(float);

    SpikeEvent(const SpikeEvent& se)
        :frameNo(se.frameNo),
        channel(se.channel),
        amp(se.amp)
    {}

    SpikeEvent(unsigned char *buffer )
        : frameNo(*reinterpret_cast<unsigned long int*>(&buffer[8])),
        channel(*reinterpret_cast<int*>(&buffer[8+sizeof(frameNo)])),
        amp(*reinterpret_cast<float*>(&buffer[8+sizeof(frameNo)+sizeof(channel)]))
    { }
};

class EventDeserialize
{
    std::vector<SpikeEvent> spikes;
    public:
    EventDeserialize( unsigned char* buffer, unsigned int buffer_size )
    {
        for (unsigned int i=0 ; i < buffer_size ; i+=SpikeEvent::bSize )
        {
            spikes.push_back( SpikeEvent( &buffer[i] ) );
        }
    }
    const std::vector<SpikeEvent> &get_spikes() {return spikes;}
    unsigned int size(){return spikes.size();}
};


std::string send_command(zmq::socket_t *socket, std::string cmd)
{
    zmq::message_t msg(cmd.size());
    memcpy(msg.data(), cmd.data(), cmd.size());
    socket->send(msg);

    // receive back answer
    zmq::message_t msg_rdy;
    socket->recv(&msg_rdy);
    return std::string(static_cast<char*>(msg_rdy.data()), msg_rdy.size());
}

void dataRead(int detection_channel) {

    zmq::context_t *context = new zmq::context_t(1);

    // Socket to receive data from the server
    zmq::socket_t subscriber(*context, ZMQ_SUB);

    unsigned int val = 0;
    subscriber.setsockopt(ZMQ_RCVHWM, &val, sizeof(val));

    val = 10 * 20000 * 1030;
    subscriber.setsockopt(ZMQ_RCVBUF, &val, sizeof(val));

    // Subscribe to everything
    const char *filter = "";
    subscriber.setsockopt(ZMQ_SUBSCRIBE, filter, strlen(filter));

    // set timeout
    int timeout = 100;
    subscriber.setsockopt(ZMQ_RCVTIMEO, &timeout, sizeof(timeout));

    subscriber.connect("tcp://localhost:7205");


    // Socket to communicate with the API
    std::string connection = "tcp://localhost:7210";
    zmq::socket_t *api_socket = new zmq::socket_t(*context, ZMQ_REQ);

    timeout = -1;
    api_socket->setsockopt(ZMQ_RCVTIMEO,  &timeout, sizeof(timeout) );
    api_socket->connect ( connection.c_str() );

    
    // sync with the RCVMore mode stream
    while (1) {
        zmq::message_t message;
        try {
            subscriber.recv(&message);
        } catch (...) {
            continue;
        }
        int64_t more = 0; //  multipart detection
        size_t more_size = sizeof(more);
        subscriber.getsockopt(ZMQ_RCVMORE, &more, &more_size);
        if (!more)
            break;
    }

    unsigned long long blanking = 0;

    while (true) {
        zmq::message_t frameNo;
        zmq::message_t frame;
        zmq::message_t events;

        try {
            /* In case the publisher dies, make sure to synchronize again */
            subscriber.recv(&frameNo);

            int64_t more = 0;
            size_t more_size = sizeof(more);

            subscriber.getsockopt(ZMQ_RCVMORE, &more, &more_size);
            if (more)
                subscriber.recv(&frame);

            subscriber.getsockopt(ZMQ_RCVMORE, &more, &more_size);
            if (more) {
                subscriber.recv(&events);
            }
        } catch (...) {
        }

        unsigned long long frame_no = 0;
        memcpy((void *)&frame_no, (void *)frameNo.data(), 6);

        // data is equivalent to: float data[frame.size() / sizeof(float)]
        float *data = (float*) frame.data();

        if (blanking)
            blanking--;

        EventDeserialize e(static_cast<unsigned char*>(events.data()), events.size());
        const std::vector<SpikeEvent> & spikes = e.get_spikes();
        for (int i=0;i<spikes.size();i++) {
            //std::cerr << i << " Spike on channel " << spikes[i].channel 
            //    << " with amplitude " << spikes[i].amp << "\n";

            int chan = spikes[i].channel;
            if (chan == detection_channel && blanking==0)
            {
                std::cout << "Saw a spike on " << detection_channel << std::endl;
                std::string reply = send_command(api_socket, "sequence_send close_loop");

                blanking = 200 * 20;// 100ms

                if (reply!="OK") {
                    std::cerr << "An error occured: " << reply << "\n";
                    std::cerr << send_command(api_socket, "get_errors");
                }
            }
        }
    }
}



int main(int argc, char *argv[]) {
    if (argc != 2) {
        std::cerr << "Call with: " << argv[0] << " [detection_channel]" << std::endl;
        exit(1);
    }

    int detection_channel = atoi(argv[1]);

    dataRead(detection_channel);

    return 0;
}
