#!/usr/bin/python
# -*- coding: utf-8

import struct
import maxlab.apicomm as comm
import maxlab.pycompat as pycompat

class Stream(object):

    @staticmethod
    def _deserialize(ret):
        size_str = ret.split(',')[0]
        size = int(size_str)
        buf = pycompat.encode(ret[len(size_str)+1:])
        fmt = '=%df' % size
        return list(struct.unpack(fmt, buf))

    @staticmethod
    def start_demodulate(freq):
        with comm.api_context() as api:
            api.send("stream_set_demodulate " + str(freq))

    @staticmethod
    def stop_demodulate():
        with comm.api_context() as api:
            api.send("stream_set_demodulate 0")

    @staticmethod
    def get_amplitudes():
        with comm.api_context() as api:
            return Stream._deserialize(api.send("stream_get_amplitudes "))

    @staticmethod
    def get_mean():
        with comm.api_context() as api:
            return Stream._deserialize(api.send("system_mean "))
