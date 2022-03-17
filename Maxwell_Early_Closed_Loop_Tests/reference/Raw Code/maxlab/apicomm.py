#-*- coding: utf-8

import os
import socket
from time import time as currenttime
from contextlib import contextmanager
import maxlab.pycompat as pycompat

ENDMARKER='\r\n###'

BUFSIZE = 1024

ENDC = '\033[0m'
FAIL = '\033[91m'

class ApiComm:
    
    def __init__(self, host='localhost', port=7215, timeout=None):
        # open socket and set options
        # port used to be 6021 -> change it to base_port + 15
        try:
            port = int(os.environ['MXW_BASE_PORT']) + 15
        except KeyError:
            port = 7200 + 15
        except ValueError:
            port = 7200 + 15
        except:
            print("Unhandled exception.")
            port = 7200 + 15

        self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if timeout:
                self.serversocket.settimeout(timeout)
            # connect
            self.serversocket.connect((host, int(port)))
        except socket.error:
            self.shutdown()
            raise
        
    def __exit__(self, *_):
        self.shutdown()

    def send(self, msg, timeout=60):
        # decorate the message with the end marker
        tosend = msg + ENDMARKER

        try:
            # write request
            self.serversocket.sendall(pycompat.encode(tosend))

            # give timeout seconds time to get the whole reply
            timeout_time = None
            if timeout:
                timeout_time = currenttime() + timeout
            
            # read response
            data = ""
            while ENDMARKER not in data:
                newdata = self.serversocket.recv(BUFSIZE) # blocking read
                newdata = pycompat.decode(newdata)
                if not newdata:
                    raise socket.error('server closed connection')
                if timeout_time is not None and currenttime() > timeout_time:
                    raise socket.error('getting response took too long')
                data += newdata
            data = data[:data.find(ENDMARKER)]
            if data == "Error":
                print(FAIL + "\nError with: \"" + msg + "\"" + ENDC)
            return data
        except socket.error:
            print('error during server query')
            self.shutdown()
            raise

    def shutdown(self):
        """Do our best to close the socket."""
        if self.serversocket is None:
            return
        try:
            self.serversocket.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass
        try:
            self.serversocket.close()
        except socket.error:
            pass

        
# port used to be 6021 -> change it to base_port + 100

@contextmanager
def api_context(host='localhost', port=7215, timeout=None):
    """Context manager for api communication
    Usage:
        with api_context(host, port, timeout) as api:
            do operations on api
    """
    api = None
    try:
        api = ApiComm(host, port, timeout)
        yield api
    finally:
        api.shutdown()
