#include <vector>
#include <fstream>
#include <iostream>
#include <zmq.hpp>


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
    zmq::socket_t subscriber_filter(*context, ZMQ_SUB);
    zmq::socket_t subscriber_raw(*context, ZMQ_SUB);

    unsigned int val = 0;
    subscriber_filter.setsockopt(ZMQ_RCVHWM, &val, sizeof(val));
    subscriber_raw.setsockopt(ZMQ_RCVHWM, &val, sizeof(val));

    val = 10 * 20000 * 1030;
    subscriber_filter.setsockopt(ZMQ_RCVBUF, &val, sizeof(val));
    subscriber_raw.setsockopt(ZMQ_RCVBUF, &val, sizeof(val));

    // Subscribe to everything
    const char *filter = "";
    subscriber_filter.setsockopt(ZMQ_SUBSCRIBE, filter, strlen(filter));
    subscriber_raw.setsockopt(ZMQ_SUBSCRIBE, filter, strlen(filter));

    // set timeout
    int timeout = 100;
    subscriber_filter.setsockopt(ZMQ_RCVTIMEO, &timeout, sizeof(timeout));
    subscriber_raw.setsockopt(ZMQ_RCVTIMEO, &timeout, sizeof(timeout));

    subscriber_filter.connect("tcp://localhost:7205");
    subscriber_raw.connect("tcp://localhost:7204");

    // Socket to communicate with the API
    std::string connection = "tcp://localhost:7210";
    zmq::socket_t *api_socket = new zmq::socket_t(*context, ZMQ_REQ);

    timeout = -1;
    api_socket->setsockopt(ZMQ_RCVTIMEO,  &timeout, sizeof(timeout) );
    api_socket->connect ( connection.c_str() );

   // Initialize poll set
    zmq::pollitem_t poll_sockets[] = {
        {(void *)subscriber_filter, 0, ZMQ_POLLIN, 0},
        {(void *)subscriber_raw,    0, ZMQ_POLLIN, 0}
        };

    unsigned long long event_frame_no = 0;
    float last_data = 1000;

    while (1) {
        // need to catch for exception, as Ctrl-C can throw
        try {
            zmq::poll(&poll_sockets[0], 2, 10);
        } catch (...) {
            std::cerr << "zmq::poll throws...";
            continue;
        }

        if (poll_sockets[0].revents & ZMQ_POLLIN) {

            zmq::message_t frameNo;
            zmq::message_t frame;
            zmq::message_t events;

            try {
                subscriber_filter.recv(&frameNo);

                unsigned long long frame_no = 0;
                memcpy((void *)&frame_no, (void *)frameNo.data(), 6);

                int64_t more = 0;
                size_t more_size = sizeof(more);

                subscriber_filter.getsockopt(ZMQ_RCVMORE, &more, &more_size);
                if (more)
                    subscriber_filter.recv(&frame);

                float *data = (float*) frame.data();

                subscriber_filter.getsockopt(ZMQ_RCVMORE, &more, &more_size);
                if (more)
                    subscriber_filter.recv(&events);

            } catch (...) {
            }
        }

        if (poll_sockets[1].revents & ZMQ_POLLIN) {

            zmq::message_t frameNo;
            zmq::message_t frame;
            zmq::message_t events;

            try {
                subscriber_raw.recv(&frameNo);

                unsigned long long frame_no = 0;
                memcpy((void *)&frame_no, (void *)frameNo.data(), 6);

                int64_t more = 0;
                size_t more_size = sizeof(more);

                subscriber_raw.getsockopt(ZMQ_RCVMORE, &more, &more_size);
                if (more)
                    subscriber_raw.recv(&frame);

                float *data = (float*) frame.data();

                if (data[detection_channel]<0 && last_data>0) {
                    std::string reply = send_command(api_socket, "mea_set_dac 0 10 10");

                    event_frame_no = frame_no;

                    if (reply!="OK") {
                        std::cerr << "An error occured: " << reply << "\n";
                        std::cerr << send_command(api_socket, "get_errors");
                    }
                }

                if (data[detection_channel] > 0 && last_data < 0) {
                    int frame_delta = static_cast<int>(frame_no - event_frame_no);
                    std::cout << frame_delta/20.0 << std::endl;
                }

                last_data = data[detection_channel];

                subscriber_raw.getsockopt(ZMQ_RCVMORE, &more, &more_size);
                if (more)
                    subscriber_raw.recv(&events);

            } catch (...) {
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

    if (detection_channel<0 || detection_channel>1025) detection_channel=0;

    dataRead(detection_channel);
    return 0;
}
