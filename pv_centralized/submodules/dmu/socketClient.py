# Copyright (c) 2020 Manuel Pitz, RWTH Aachen University
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT>, at your option. This file may not be
# copied, modified, or distributed except according to those terms.




from concurrent.futures import thread
from logging.handlers import SocketHandler
import select
import socket
import logging, copy, json, uuid
from dmu import dmu
from dmu.utils import varargsToList
from dmu.socketDataType import dataType
import time, sys
from struct import *
import threading

class DataHandler:
    @classmethod
    def handleVillasBinary(cls, data, dType, seqNumber):
        dataCount = len(data)
        packet = pack('!BBH', 0b00100000, 0, dataCount)# @todo check why this is correct with villas

        packet = packet + pack('!I', seqNumber)
        

        now = time.time()

        packet = packet + pack('!I', int(now))

        nanosec = int((now - float(int(now))) * 1e9)
        packet = packet + pack('!I', nanosec)

        # @todo datatype validation is missing
        for elm in data:
            packet = packet + pack('!' + dType, elm)
            
        return packet
    
    @classmethod
    def handleGTNET(cls, data, dType):
        packet = bytes()
        for elm in data:
            packet = packet + pack('!' + dType, elm)
            
        return packet

class socketClient:

    # Constructor
    def __init__(self, host, port, dmuObj, dType, handler = "villasBinary"):
        
        # Initialize logger
        self._log = logging.getLogger(__name__)

        # Dmu configuration
        self.seqNumber = 0
        self.host = host
        self. port = port
        self._dmuObj = dmuObj
        self._publisherParameters = {}
        self.dType = dType
        self.handler = handler

        # Socket configuration
        self._socketHandle = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
           
    # Socket 
    #@todo this version cannot handle fragmentation. add that feature!
    def handleSocketSend(self, data, uuid, name, subelements, context):

        if isinstance(data, (float, int)):
            data  = [data]
        elif not isinstance(data, list):
            self._log.warn("Datatype %s not allowed for villas binary", type(data))
            return -1
        
        if self.handler == "villasBinary":
            packet = DataHandler.handleVillasBinary(data, self.dType.value, self.seqNumber)
            self.seqNumber = self.seqNumber + 1
        elif self.handler == "GTNET":        
            packet = DataHandler.handleGTNET(data, self.dType.value)
        else:
            self._log.warning("Handler %s could not be found", self.handler)
            return

        

        self._socketHandle.sendto(packet, (self.host, self.port))



    def attachPublisher(self, name,  *args):
        '''
        This function connect a dmu element with the tx handles for socket connection 
        '''
        args = varargsToList(*args)

        # add monitor to dmu object
        uuid = self._dmuObj.addElmEvent(self.handleSocketSend, name, args)
        

        if uuid != False:
            if not uuid in self._publisherParameters:
                self._publisherParameters.update({uuid : {}})
            else:
                self._log.error("Dublicate uuid. This really should not happen. %s", uuid)
        else:
            self._log.warning("could not add monitor to %s->%s",  name, '->'.join(args))

        return False

    