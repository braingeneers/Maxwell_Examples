#!/usr/bin/python
# -*- coding: utf-8

import math
import time

import maxlab.apicomm as comm
import maxlab.stream as stream

def initialize(wells=None):
    with comm.api_context() as api:
        if wells is None:
            api.send("system_initialize")
        else:
            api.send("system_initialize_wells " + ','.join([str(w) for w in wells]))

def activate(wells):
    with comm.api_context() as api:
        api.send("system_set_activated_wells " + ','.join([str(w) for w in wells]))

def offset():
    with comm.api_context() as api:
        api.send("system_offset")
        time.sleep(5)

def hpf(cutoff):
    if (cutoff=="1Hz"):
        cutoff_value=4095
    elif (cutoff=="300Hz"):
        cutoff_value=1100
    else:
        raise ValueError("Not a valid high-pass parameter: " + str(cutoff) + "\n" + \
                         "Allowed values are: '1Hz' and '300Hz'" )
    with comm.api_context() as api:
        api.send("system_hpf " + str(cutoff))

def set_gain(gain):
    with comm.api_context() as api:
        api.send("system_gain " + str(gain))

def get_mean():
    return stream.Stream.get_mean()

def percentile(values, percent):
    """Find the percentile of a list of values.

    @parameter values - is a list of values. Note values MUST BE already sorted.
    @parameter percent - a float value from 0.0 to 1.0.

    @return - the percentile of the values
    """
    if not values:
        return None
    k = (len(values)-1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    d0 = values[int(f)] * (c-k)
    d1 = values[int(c)] * (k-f)
    return d0+d1
