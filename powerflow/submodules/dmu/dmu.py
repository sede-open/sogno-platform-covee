# Copyright (c) 2020 Manuel Pitz, RWTH Aachen University
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT>, at your option. This file may not be
# copied, modified, or distributed except according to those terms.
import logging, copy, threading, time, uuid, queue
from typing import Any, List
from inspect import signature

dataStruct = {"data": None, "notifier": None, "lock": None, "lastModified": 0}

rxSyncStruct = {
    "action": [],
    "thread": [],
    "threadRun": True,
    "subelements": [],
    "lastTrigger": 0,
    "triggerCounter": 0,
}

class Dmu:
    """Core of the DMU Library.
    """
    
    def __init__(self):
        """Initializes a new DMU instance.
        """
        self.__rxSyncRegestry = {}
        self.__data = {}
        self.__log = logging.getLogger(__name__)
        self.__log.info("Start dmu")
        self._dmuTargets = []  # a list of other dmus to sync with
        
 
        self.initQueue()

    def __del__(self):
        """Cleans up the DMU instance and releases all resources (!!including all event handlers!!)
        """
        self.cleanup()
        self.runDequeue = False
        

    def cleanup(self):
        """Cleans up the DMU instance and releases all resources (!!including all event handlers!!)
        """
        names = list(self.__data.keys())
        for name in names:
            self.rmElm(name)
        self.__log.info("Cleanup dmu")


    def addSubElm(self, data, name, *args):
        """Adds a subelement of to the element with the given path.  

        Args:
            data (): The data to be added as a subelement. \n
            name (str): Name of the root element. \n
            args ([str]): Path from the root element to the parent element of the subelement. 
        Returns:
            int: 
                -2 in case of an error, \n
                -1 in case of success of a dictionary, \n
                i >= 0 in case of success of a list where i is the index of the new element.
        Examples:
        Let dmu be an instance of the DMU class and filled with a dictionary {"root": {"parent": {}}}.
        ```python 
        dmu.addSubElm({"test": "var"}, "root", "parent") 
        ```
        would append a new dictionary to the list of subelements of the element with the path "root->parent" and return -1.
        
        ```python
        dmu.addSubElm([1,2,3,4], "root", "parent")
        ```
        would append a new list to the element of "parent", and return -1.
        """
        name, args = self.__handleListArguments(name, *args)
        if not self.elmExists(name, args):
            if not self.elmExists(name, args[:-1]):
                self.__log.error(
                    "Motherelements dont't exist %s->%s",
                    name,
                    "->".join(str(x) for x in args[:-1]),
                )
                return -2

        self.__data[name]["lock"].acquire()

        target = self.__data[name]
        args.insert(0, "data")
        keyCount = len(args)
        loopIteration = 0
        for key in args[:-1]:
            if (loopIteration >= (keyCount - 1)) or (
                not isinstance(target[key], dict) and not isinstance(target[key], list)
            ):
                break
            target = target[key]
            loopIteration = loopIteration + 1

        if isinstance(target, dict):
            target.update({args[-1]: copy.deepcopy(data)})
            ret = -1
        elif isinstance(target, list):
            target.append(copy.deepcopy(data))
            ret = len(target) - 1

        self.generateNotifiers(
            self.__data[name]["notifier"], name, self.__data[name]["data"]
        )
        self.__data[name]["lock"].release()

        return ret
    
    def addElm(self, name, data, notify=False):
        self.__log.warning("You are using a deprecated function addElm use add instead. Attention name and data parmeters are flipped!")
        self.add(data, name, notify=notify)

    def add(self, data, name, notify = False):
        """Adds a new element with the initial data to the DMU instance. The given data will be copied and stored in the dmu instance.

        Args:
            data (any): The initial data of the new element \n
            name (str): The key (name) of the new element \n
            notify (bool, optional): Whether to notify the event handlers on creation. Defaults to False.

        Returns:
            bool: Whether the operation was successful or not.
        
        Examples:    
        
            ```python
            dmu_obj = dmu()
            dmu_obj.addElm("test", "test value")
            dmu_obj.addElm("test2", {"testLevel1": "test value"})
            ```
            
            
            The first creates a new dmu element with the name "test" and the value "test value". 
            The dmu structure would be `{"test": "test value"}`

            The second creates a new dmu element with the name "test2" and the value {"testLevel1": "test value"}.
            The dmu structure would be `{"test": "test value", "test2": {"testLevel1": "test value"}}`.
        """

        if name in self.__data:
            self.__log.error("Element %s already exists", name)
            return False
        else:
            dataStruct["data"] = data
            self.__data.update({name: copy.deepcopy(dataStruct)})
            self.__data[name]["lock"] = threading.Lock()
            self.__data[name]["lock"].acquire()
            self.__data[name]["notifier"] = {}
            self.__data[name]["notifier"].update(
                {"handle": threading.Condition(), "sub": {}}
            )
            self.generateNotifiers(
                self.__data[name]["notifier"], name, self.__data[name]["data"]
            )

            self.__data[name]["lock"].release()
            if notify:
                with self.__data[name]["notifier"]["handle"]:
                    self.__data[name]["notifier"]["handle"].notify_all()
            return True
        return False


    def rmElm(self, name):
        self.__log.warning("You are using a deprecated function rmElm use rm instead.")
        self.rm(name)
        
    def rm(self, name):
        """Removes an element from the dmu instance.

        Args:
            name (str): The name of the element to remove.
        """
        if self.elmExists(name):
            uuidList = []

            if name in self.__rxSyncRegestry:
                for uuid in self.__rxSyncRegestry[
                    name
                ]:  # aquire a list of uuids for the remove later
                    uuidList.append(uuid)
                for uuid in uuidList:
                    self.rmElmEvent(name, uuid)

            self.cleanNotifiers(self.__data[name]["notifier"], name)
            del self.__data[name]

        else:
            self.__log.warning("Try to remove non existing element " + name)

    def notifyElmEvent(self, name, uuid):
        """
        This function can notify a specific event
        """

        subelemnts = self.__rxSyncRegestry[name][uuid]["subelements"]

        notifier = self.getNotifierHandle(self.__data[name]["notifier"], subelemnts)
        with notifier:
            notifier.notify()

    def generateNotifiers(self, target, name, data=None):
        """
        this function generates all notifiers and is auto called by dmu itself to update new values
        """
        if isinstance(data, dict):  # register notifiers for each subelements
            for key in data:
                if not key in target["sub"]:  # create if not exists
                    target["sub"].update(
                        {key: {"handle": threading.Condition(), "sub": {}}}
                    )
                self.generateNotifiers(target["sub"][key], name, data[key])

    def cleanNotifiers(self, target, name, subElmList=None):
        """
        this function cleans orphaned values from the notifier list and also from the rx sync regestry
        """
        if subElmList is None:
            subElmList = []
        removeKeys = []
        removeSubElmList = []
        for key in target["sub"]:
            subElmList.append(key)
            self.cleanNotifiers(target["sub"][key], name, copy.deepcopy(subElmList))
            if not self.elmExists(name, subElmList):
                removeKeys.append(key)
                removeSubElmList.append(copy.deepcopy(subElmList))
            del subElmList[-1]

        for i in range(len(removeKeys)):
            uuid = self.getThreadUuid(name, removeSubElmList[i])
            if uuid != None:
                self.__log.warning(
                    "Remove orphaned notifier. Maybe you overwrote a subelement unintentionally. %s->%s",
                    name,
                    "->".join(self.__rxSyncRegestry[name][uuid]["subelements"]),
                )
                self.rmElmEvent(name, uuid)
            del target["sub"][removeKeys[i]]

    def buildNamesMap(self, data, listIn):
        """buildNamesMap is a recursive function to build a list of all subelements of all dicts in the data structure (dicts and lists)

        Args:
            data (any): The data structure to build the list from \n
            listIn (list[str]): The list of subelement-keys to the current position in the data structure passed down from the parent call. Start at []

        Returns:
            list[str]: The complete list of subelement-keys.
        """
        ret = []
        if isinstance(data, dict):
            if not data:
                ret.append("/".join(listIn))
            for key, value in data.items():
                listIn.append(key)
                returnList = self.buildNamesMap(value, copy.deepcopy(listIn))
                listIn.pop()
                ret = ret + copy.deepcopy(returnList)
        elif (
            isinstance(data, list) and len(data) < 10
        ):  # @todo this 10 is not a good approach think about something better
            if not data:
                ret.append("/".join(listIn))
            for i, value in enumerate(data):
                listIn.append(str(i))
                returnList = self.buildNamesMap(value, copy.deepcopy(listIn))
                listIn.pop()
                ret = ret + copy.deepcopy(returnList)
        else:
            # elif isinstance(data, list) or isinstance(data,int) or isinstance(data,float):
            ret.append("/".join(listIn))
        return ret

    def getAllElementNames(self):
        """getAllElementNames returns a list of all element-keys and their subelement-keys etc... in the dmu store.

        Returns:
            list[str]: The list of all keys
        """
        elm = []
        for key in self.__data:
            elm = elm + self.buildNamesMap(self.__data[key]["data"], [key])

        return elm

    def elmEventThread(self, name, uuid, startEvent, context):
        """elmEventThread is the thread function for an event handler. The thread is started when the event handler is 

        Args:
            name (str): the element key
            uuid (str): uuid of the event handler
            startEvent (threading.Event): The event that signals the thread has startet.
            context (any): Context passed down to the thread
        """

        startEvent.set()


        while self.__rxSyncRegestry[name][uuid]["threadRun"]:
            if not self.elmExists(name):
                continue
            status, data = self.getDataSubsetUpdate(
                name,
                self.__rxSyncRegestry[name][uuid]["subelements"]
            )
            if not self.__rxSyncRegestry[name][uuid][
                "threadRun"
            ]:  # handle trigger by thread temrination action
                continue
            if not status:  # wait statemant ran into timeout
                continue
            # legecy fix to enable 4 parameter functions including the uuid of the elmEventThread
            paramCount = len(
                signature(self.__rxSyncRegestry[name][uuid]["action"]).parameters
            )
            if paramCount == 3:
                self.__rxSyncRegestry[name][uuid]["action"](
                    data, name, self.__rxSyncRegestry[name][uuid]["subelements"]
                )
                self.__log.warning(
                    "You are using a deprecated function call type for %s. This function call with 3 parameters will soon be removed. Check Readme",
                    self.__rxSyncRegestry[name][uuid]["action"].__name__,
                )
            elif paramCount == 4:
                self.__rxSyncRegestry[name][uuid]["action"](
                    data, uuid, name, self.__rxSyncRegestry[name][uuid]["subelements"]
                )
                self.__log.warning(
                    "You are using a deprecated function call type for %s. This function call with 4 parameters will soon be removed. Check Readme",
                    self.__rxSyncRegestry[name][uuid]["action"].__name__,
                )
            elif paramCount == 5:
                self.__rxSyncRegestry[name][uuid]["action"](
                    data,
                    uuid,
                    name,
                    self.__rxSyncRegestry[name][uuid]["subelements"],
                    context,
                )
            else:
                self.__log.error(
                    "Try to call %s with wrong number of parameter %i",
                    self.__rxSyncRegestry[name][uuid]["action"].__name__,
                    paramCount,
                )
            self.__rxSyncRegestry[name][uuid]["lastTrigger"] = time.time()
            self.__rxSyncRegestry[name][uuid]["triggerCounter"] = self.__rxSyncRegestry[name][uuid]["triggerCounter"] + 1
            self.__rxSyncRegestry[name][uuid]["callbackDoneEvent"].clear()

    def getThreadUuid(self,name, *args):
        '''
            returns the thread uuid if exists otherwise none.
            The thread uuid is the internal uuid of the event thread.
        '''

        name, args = self.__handleListArguments(name, *args)

        if not name in self.__rxSyncRegestry:
            logging.warn("No rx handle registered for %s", name)
            return None

        for key in self.__rxSyncRegestry[name]:
            if self.__rxSyncRegestry[name][key]["subelements"] == args:
                return key

        return None

    def recursiveEventHandle(self, data, uuid, name, args):
        '''This function is the corresbonding handler to attachRecursiveEvent it will specifically trigger all subelements that are below "name, args"'''
        for eventUuid in self.__rxSyncRegestry[name]:
            if eventUuid == uuid:
                continue
            elm = self.__rxSyncRegestry[name][eventUuid]
            execEvent = True
            for i in range(len(elm["subelements"])):
                if i >= len(args):
                    break
                if elm["subelements"][i] != args[i]:
                    execEvent = False
            if execEvent is True:
                notifier = self.getNotifierHandle(
                    self.__data[name]["notifier"], elm["subelements"]
                )
                with notifier:
                    notifier.notify_all()
        return

    def attachRecursiveEvent(self, name, *args):
        """
        With this function a recursive trigger can be created.
        This means that all subelements will be triggerd when this element is updated
        """
        return self.addElmEvent(self.recursiveEventHandle, name, *args)

    def detachRecursiveEvent(self, name, uuid):
        return self.rmElmEvent(name, uuid)

    def addRx(self, handle, name, *args):
        self.__log.warning(
            "You are using a deprecated function addRx for "
            + name
            + "->"
            + "->".join(args)
            + ". This function will soon be removed. Consider using addElmEvent instead"
        )
        self.addElmEvent(handle, name, *args)

    def addElmMonitor(self, handle, name, *args):
        self.__log.warning(
            "You are using a deprecated function addElmMonitor for "
            + name
            + "->"
            + "->".join(args)
            + ". This function will soon be removed. Consider using addElmEvent instead"
        )
        self.addElmEvent(handle, name, *args)


    def addElmEvent(self, handle, name, *args, blockUntilStart = True, context = None):
        """Add a new event handler to an element

        Args:
            handle (callable): The handler function that will be called when an event is triggered on the element 
            name (str): Name of the element \n
            blockUntilStart (bool, optional): Whether to block the event handler thread until the start event is invoked. Defaults to True. \n
            context (any | None, optional): A set of values given to the event handler on each invocation. Defaults to None.

        Returns:
            str: uuid of the event handler that can be used to remove the event handler
        """
        
        name, args = self.__handleListArguments(name, *args)

        if not self.elmExists(name, args):
            logging.warn(
                "One or more element do not exist %s->%s", name, "->".join(args)
            )
            return False

        if not name in self.__rxSyncRegestry:
            self.__rxSyncRegestry.update({name: {}})

        uuidStr = str(uuid.uuid1())
        self.__rxSyncRegestry[name][uuidStr] = copy.deepcopy(rxSyncStruct)

        self.__rxSyncRegestry[name][uuidStr]["action"] = handle
        self.__rxSyncRegestry[name][uuidStr]["subelements"] = args
        self.__rxSyncRegestry[name][uuidStr]["callbackDoneEvent"] = threading.Event()
        startEvent = threading.Event()
        thread = threading.Thread(
            target=self.elmEventThread, args=(name, uuidStr, startEvent, context)
        )
        self.__log.debug("Add event action for %s->%s", name, "->".join(args))
        self.__rxSyncRegestry[name][uuidStr]["thread"] = thread
        thread.start()
        if blockUntilStart:
            startEvent.wait()
        return uuidStr

    def eventLastUpdate(self, name, uuid):
        """
        This function returns the last execution of the event thread
        It can also be used to check when there was the last update

        return -1 means error
        """
        if not name in self.__rxSyncRegestry:
            logging.warn("Element does not exist %s", name)
            return -1

        if not uuid in self.__rxSyncRegestry[name]:
            logging.warn("UUID does not exist %s", uuid)
            return -1

        return self.__rxSyncRegestry[name][uuid]["lastTrigger"]

    def eventTriggerCounter(self, name, uuid):
        """
        This function returns the counted executions of a event thread

        return -1 means error
        """
        if not name in self.__rxSyncRegestry:
            logging.warn("Element does not exist %s", name)
            return -1

        if not uuid in self.__rxSyncRegestry[name]:
            logging.warn("UUID does not exist %s", uuid)
            return -1

        return self.__rxSyncRegestry[name][uuid]["triggerCounter"]

    def rmElmMonitor(self, name, uuid):
        self.__log.warning(
            "You are using a deprecated function rmElmMonitor. This function will soon be removed. Consider using rmElmEvent instead"
        )
        return self.rmElmEvent(name, uuid)

    def rmRx(self, name, uuid):
        self.__log.warning(
            "You are using a deprecated function rmRx. This function will soon be removed. Consider using rmElmEvent instead"
        )
        return self.rmElmEvent(name, uuid)

    def rmElmEvent(self, name, uuid):
        """Removes an event handler from an element

        Args:
            name (str): The name of the dmu element \n
            uuid (str): The uuid of the event handler that was returned by addElmEvent

        Returns:
            bool: Whether the event handler was removed successfully
        """

        if not name in self.__rxSyncRegestry:
            logging.warn("Try to remove RX thread from non existing object %s", name)
            return False

        if not uuid in self.__rxSyncRegestry[name]:
            logging.warn("RX element does not exist %s->%s", name, uuid)
            return False

        threadHandle = self.__rxSyncRegestry[name][uuid]["thread"]
        self.__rxSyncRegestry[name][uuid]["threadRun"] = False
        self.notifyElmEvent(name, uuid)
        threadHandle.join()
        logging.info("Thread with uuid %s was terminated", uuid)
        del self.__rxSyncRegestry[name][uuid]

        return True

    def setDataSubsetList(self, args):
        """
        use list argument for setting the data subset
        args[0] is the value
        args[1] is element name
        args[2:] is path to subelements
        """
        return self.setDataSubset(args[0], args[1], args[2:])

    def setDataSubset(self, data, name, *args):
        self.__log.warning("setDataSubset is deprecated, use setData instead")
        return self.setData(data, name, *args)
    
    def dequeueThread(self):
        
        while self.runDequeue:
            #self.__log.info("Try dequeue")
            if self.getQueueSize() > 0:
                e = self.setDataQueueData.get()
                #no event attached to this element
                if not e["name"] in self.__rxSyncRegestry:
                    #self.__log.info("Skip queue")
                    self.setData(e["data"], e["name"], e["args"])
                else:
                    while True:
                        flag = False
                        for uuid in self.__rxSyncRegestry[e["name"]]:
                            if self.__rxSyncRegestry[e["name"]][uuid]["callbackDoneEvent"].is_set():
                                flag = True
                                break
                        if not flag:
                            break
                        #self.__log.info("delay setData %s", e["name"])
                        time.sleep(0.001)
                    #self.__log.info("exec setData %s data: %d", e["name"], e["data"])
                    for uuid in self.__rxSyncRegestry[e["name"]]:
                        self.__rxSyncRegestry[e["name"]][uuid]["callbackDoneEvent"].set()
                    self.setData(e["data"], e["name"], e["args"])


    
    def setDataQueue(self, data: Any, name: str, *args):
        #self.__log.info("setDataQueue to %s\t%s", name, __name__)
        name, args = self.__handleListArguments(name, *args)
        e = {
            "data" : copy.deepcopy(data),
            "name" : name,
            "args" : copy.deepcopy(args)
        }
        self.setDataQueueData.put(e)
    
    def initQueue(self):
        self.setDataQueueData = queue.Queue()
        self.runDequeue = True
        self.dequeueTrheadHandle = threading.Thread(
            target=self.dequeueThread, args=()
        )
        self.dequeueTrheadHandle.start()

    
    def getQueueSize(self):
        return self.setDataQueueData.qsize()


    def setData(self, data: Any, name: str, *args):
        """Write data into a subset of an element

        Args:
            data (any): The data that should be written \n
            name (str): the name of the element \n
            args (list[str]): The subset of the element that should be written to

        Returns:
            bool: Whether the data was written successfully
        """
        name, args = self.__handleListArguments(name, *args)

        if not self.elmExists(name, args):
            self.__log.warn(
                "One or more element do not exist %s->%s", name, "->".join(args)
            )
            return False

        ret = True
        noNotify = False  # used to handle the case of writing to an array
        if not name in self.__data:
            self.__log.error("Element %s does not exist", name)
            ret = False
        else:
            self.__data[name]["lock"].acquire()
            target = self.__data[name]
            args.insert(0, "data")
            lastKey = ""
            keyCount = len(args)
            loopIteration = 0
            for key in args:
                if isinstance(target, dict):
                    if key not in target:
                        self.__log.error("Element %s does not exist in %s ", key, name)
                        ret = False
                        break
                elif isinstance(target, list):
                    if key > len(target) - 1:
                        self.__log.error("Element %s does not exist in %s ", key, name)
                        ret = False
                        break
                lastKey = key
                if (
                    not isinstance(target[key], dict)
                    and not isinstance(target[key], list)
                ) or (loopIteration >= (keyCount - 1)):
                    break
                target = target[key]
                loopIteration = loopIteration + 1
            if ret is True:
                target[lastKey] = copy.deepcopy(data)

            self.generateNotifiers(
                self.__data[name]["notifier"], name, self.__data[name]["data"]
            )
            self.cleanNotifiers(self.__data[name]["notifier"], name)

            self.__data[name]["lock"].release()
            if ret is True:
                notifier = self.getNotifierHandle(
                    self.__data[name]["notifier"], args[1:]
                )
                with notifier:
                    notifier.notify_all()

        return ret

    def getNotifierHandle(self, target, argsList):
        if len(argsList) > 0 and argsList[0] in target["sub"]:
            return self.getNotifierHandle(target["sub"][argsList[0]], argsList[1:])
        else:
            return target["handle"]
        
    def getDataSubset(self, name, *args):
        self.__log.warning(
            "You are using a deprecated function getDataSubset. This function will soon be removed. Consider using getData instead."
        )
        return self.getData(name, *args)

    def getData(self,name,*args):
        """Read data from a subset of an element

        Args:
            name (str): The name of the element \n
            args (list[str]): The subset of the element that should be read from

        Returns:
            any: The data that was read 
        """
        ret = None
        name, args = self.__handleListArguments(name, *args)
        if not name in self.__data:
            self.__log.error("Element %s does not exist", name)
        else:
            self.__data[name]["lock"].acquire()
            target = self.__data[name]["data"]
            try:
                for arg in args:
                    if isinstance(target, list):
                        arg = int(arg)  # make sure we convert it to integer
                    target = target[arg]
                ret = copy.deepcopy(target)
            except KeyError:
                self.__log.error(
                    "Could not find the requested data in element {}: {}".format(
                        name, args
                    )
                )
            finally:
                self.__data[name]["lock"].release()
                return ret

    def getDataSubsetUpdate(self, name, *args):
        """
        reads a subset from a data element
        This is a blocking version of getDataSubset
        """
        data = None
        status = True
        name, args = self.__handleListArguments(name, *args)
        if not name in self.__data:
            self.__log.error("Element %s does not exist", name)
        else:
            notifier = self.getNotifierHandle(self.__data[name]["notifier"], args)
            with notifier:
                notifier.wait()
            self.__data[name]["lock"].acquire()
            target = self.__data[name]["data"]
            try:
                for arg in args:
                    target = target[arg]
                data = copy.deepcopy(target)
            except KeyError:
                self.__log.exception("Could not find the requested data")
            finally:
                self.__data[name]["lock"].release()
                return status, data

    def elmExists(self, name, *args):
        """elmExists checks whether an element exists in the dmu

        Args:
            name, *args(str): The key / path to be checked

        Returns:
            bool: Whether the element exists 
        """
        ret = None
        name, args = self.__handleListArguments(name, *args)

        if name in self.__data:
            ret = True
        else:
            ret = False

        if ret is not False and len(args) > 0:  # check submelements
            target = self.__data[name]["data"]
            for arg in args:
                if isinstance(target, dict):
                    if arg in target:
                        target = target[arg]
                        continue
                    else:
                        ret = False
                elif isinstance(target, list):
                    try:  # try to access the vlaue
                        target = target[int(arg)]
                        continue
                    except:
                        ret = False
                break

        return ret

    def __handleListArguments(self, name, *args):
        """handles cases of lists and values as arguements"""

        if isinstance(name, list):
            # if we pass only a list, instead of a single name and than comma sperated args, extract the first element as the name
            return str(name[0]), copy.deepcopy(name[1:])

        if isinstance(args, tuple):
            if len(args) == 1:
                if isinstance(args[0], list):
                    return str(name), copy.deepcopy(args[0])
                elif isinstance(args[0], tuple):
                    return str(name), copy.deepcopy(list(args[0]))
                else:
                    return str(name), copy.deepcopy([args[0]])
            elif len(args) > 1:
                return str(name), copy.deepcopy(list(args))
            else:
                return str(name), []
        else:
            self.__log.warning("Passed args argument not recognized. Assume empty list")
            return str(name), []

dmu = Dmu