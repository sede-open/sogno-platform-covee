import logging, threading, socket, uuid
from struct import *
from dmu.socketDataType import dataType


class DataHandler:
    @classmethod
    def handleVillasBinary(cls, data, dType):
        pos = 0
        (h1, nodeId, dataCount) = unpack_from("!BBH", data, pos)
        pos = pos + calcsize("BBH")
        if h1 != 0b00100000:  # @todo this is not working
            logging.warning(f"Misinterpreted header version {h1} != 0b00010000")

        seqNumber = unpack_from("!I", data, pos)
        pos = pos + calcsize("I")
        blaa = calcsize("L")

        timeSec = unpack_from("!I", data, pos)
        pos = pos + calcsize("I")

        timeNano = unpack_from("!I", data, pos)
        pos = pos + calcsize("I")

        dataObjs = []
        for i in range(dataCount):
            val = unpack_from(">" + dType, data, pos)
            dataObjs.append(val[0])
            pos = pos + calcsize(dType)
            
        return dataObjs
        
    @classmethod
    def handleGTNET(cls, data, count, dType):
        dataObjs = []
        pos = 0

        for i in range(count):
            val = unpack_from(">" + dType, data, pos)
            dataObjs.append(val[0])
            pos = pos + calcsize(dType)
            
        return dataObjs

class socketServer:
    def __init__(self, host, port, dmuObj, dType, handler = "villasBinary", count = 0):
        self._log = logging.getLogger(__name__)

        # Dmu configuration
        self.seqNumber = 0
        self.host = host
        self.port = port
        self._dmuObj = dmuObj
        self._publisherParameters = {}
        self.dType = dType
        self.handler = handler
        self.count = count

        self._subscriberLock = threading.Lock()
        self._subscriber = {}

        # Socket configuration
        self._socketHandle = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self._socketHandle.bind((host, port))
        self._socketSrvThread = threading.Thread(name='socketSrv', target=self.receiveDataThreaded)
        self._socketSrvThread.start()

    def attachSubscriber(self, name: str, *args) -> uuid.UUID | int:
        """Attaches a subscriber to the socket data stream to update the given dmu data-subset

        Args:
            name, *args (str | str[]): The data-subset/path to update


        Returns:
            uuid | -1: The subscription uuid or -1 in case of an error.
        """
        args = self.__handleListArguments(*args)

        # check if the element exists
        if not self._dmuObj.elmExists(name):
            self._log.warning("DMU element %s does not exist.", name)
            return -1

        # create the element event thread
        uuidStr = str(uuid.uuid1())
        if uuidStr in self._subscriber:# If this is valid something really bad happend.
            self._log.error("Duplicate uuid.")
            return -1

        # lock _subscriber data
        with self._subscriberLock:
            # attach subscriber
            self._subscriber.update({uuidStr: {}})
            self._subscriber[uuidStr] = {
                "name": name,
                "subelements": args,
            }

        return uuid

    def detachSubscriber(self, name: str, uuid: str) -> bool:
        """
        Detaches the given subscriber of a socket-datastream to the dmu object

        :param name: Unused name of the dmu object
        :param uuid: uuid of the subscription
        :return: True if detaching was successful. False otherwise.
        """
        with self._subscriberLock:
            if not uuid in self._subscriber:
                self._log.warning("Could not find subscriber with uuid %s", uuid)
                return False

            del self._subscriber[uuid]
            return True

    # @todo this version cannot handle fragmentation. add that feature!
    def receiveDataThreaded(self):
        while True:
            # first receive only the header hopefully
            data = self._socketHandle.recv(4096)

            if self.handler == "villasBinary":
                dataObjs = DataHandler.handleVillasBinary(data, self.dType.value)
            elif self.handler == "GTNET":        
                dataObjs = DataHandler.handleGTNET(data, self.count,  self.dType.value)
            else:
                self._log.warning("Handler %s could not be found", self.handler)
                return

            # self._log.info(
            #     f"Received following information seqNumber: {seqNumber}; timeSec: {timeSec}; timeNano: {timeNano}; dataObjs: {dataObjs}")

            self._subscriberLock.acquire()
            # update dmu object
            for sub in self._subscriber:
                self._dmuObj.setDataSubset(dataObjs, self._subscriber[sub]["name"], self._subscriber[sub]["subelements"])  # set data subset with the subscriber to
                # the data stream
            self._subscriberLock.release()

    def __handleListArguments(self, *args):
        ''' handles cases of lists and values as arguements '''

        if isinstance(args, tuple):
            if len(args) == 1:
                if isinstance(args[0], list):
                    return args[0]
                elif isinstance(args[0], tuple):
                    return list(args[0])
                else:
                    return [args[0]]
            elif len(args) > 1:
                return list(args)
            else:
                return []
        else:
            self._log.warning("Passed args argument not recognized. Assume empty list")
            return []