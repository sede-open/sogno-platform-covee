# Copyright (c) 2023 Manuel Pitz, RWTH Aachen University
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT>, at your option. This file may not be
# copied, modified, or distributed except according to those terms.
from http.server import HTTPServer, BaseHTTPRequestHandler
from http.client import HTTPConnection
import logging, json, time
import threading
from typing import Any, TypedDict, Callable
import uuid

from submodules.dmu.dmu import dmu
from submodules.dmu.timer import Timer


class ServerAlreadyPublishingError(Exception):
    """Raised when the httpSRV is already publishing a dmu element

    Args:
        Exception (_type_): _description_
    """

    
class HTTPSrvSubscriber(TypedDict):
    host: str
    port: int
    dmuElm: str
    
class HTTPSrvConfig(TypedDict, total=False):
    pollerIntervalS: float
    pollerHTTPTimeoutS: float
    publisherHTTPTimeoutS: float


class httpSrv:
    """A HTTP provider. 
            Using the attachSubscriber / detachSubscriber methods a new listener (using polling!) for socket listeners use other providers
            
            Using the attachPublisher / detachPublisher methods a dmu element (or the whole store) can be made queryable.
            
            Detailed documentation on [dmu.fein-aachen.org](https://dmu.fein-aachen.org/#/providers/http)        
        """
    
    def __loadDefaultConfig(self, config: HTTPSrvConfig) -> HTTPSrvConfig:
        return {
            "pollerIntervalS": config.get("pollerIntervalS", .5),
            "pollerHTTPTimeoutS": config.get("pollerHTTPTimeoutS", 10.),
            "publisherHTTPTimeoutS": config.get("publisherHTTPTimeoutS", 10.),
        }
    
    def __init__(self, dmuObj: dmu, config: HTTPSrvConfig):
        """Init a HTTP provider. 
            Using the attachSubscriber / detachSubscriber methods a new listener (using polling!) for socket listeners use other providers
            
            Using the attachPublisher / detachPublisher methods a dmu element (or the whole store) can be made queryable.
            
            Detailed documentation on [dmu.fein-aachen.org](https://dmu.fein-aachen.org/#/providers/http)
            
        Args:
            dmuObj (dmu.dmu): The dmu object the provider acts upon
            config (dict): The configuration of the HTTP
        """
        self.__log = logging.getLogger(__name__)
        logging.getLogger('http-provider').setLevel(logging.ERROR)
        
        self.dmuObj = dmuObj
        
        self._config: HTTPSrvConfig = self.__loadDefaultConfig(config)
        
        #subscriber synch.
        self._pollerTimer = Timer(self._config["pollerIntervalS"], self._makeSubscriberFunction())
        self._pollers: dict[uuid.UUID, HTTPSrvSubscriber] = {}
        self._pollerLock = threading.Lock()

        #provider synchronization
        self._started = False
        self._startedLock = threading.Lock()
        self._httpd: HTTPServer | None = None
        
    def cleanup(self):
        """Stops all subscribers and publishers
        """
        
        self._pollerTimer.__exit__()
        self._pollers.clear()
        
        with self._startedLock:
            if not self._started:
                self.__log.warning("HTTP server already stopped")
                return
            self._started = False
        if self._httpd is not None:
            self._httpd.shutdown()
        self.__log.info("HTTP server is down")
        
    def __requestUpdate(self, subscription: HTTPSrvSubscriber) -> Any:
        conn = HTTPConnection(subscription["host"], subscription["port"], timeout=self._config["pollerHTTPTimeoutS"])
        requestURL = "/" + subscription["dmuElm"]
        conn.request("GET", requestURL)
        response = conn.getresponse()
        
        if response.status != 200:
            self.__log.error("error during synchronization status code: %s", response.status)
            raise RuntimeError("error during polling") # needs to raise exception to understand that this should not be set to dmu
        data = json.load(response)
        return data
        
    def __copyUpdate(self, subscription: HTTPSrvSubscriber, data: Any):
        if subscription["dmuElm"] != "":
            self.dmuObj.setData(data, subscription["dmuElm"])
        else:
            # TODO we must clear the entire dmu and add the new copy. Clear functionality missing in dmu
            raise NotImplementedError()


    
    def _makeSubscriberFunction(self) -> Callable:
        """Closure to create a function that will poll the currently subscribed sources for updates.

        Returns:
            Callable: The closure function
        """
        #TODO: implement asynchronous http calls and await at the end for all. (using asynchio, maybe have look at httpx)
        def poll_for_updates():
            with self._pollerLock:
                if not self._pollers:
                    return

                for subscriptionID, subscription in self._pollers.items():
                    try:
                        data = self.__requestUpdate(subscription)
                        self.__copyUpdate(subscription, data)
                    except TypeError:
                        self.__log.warning("could not deserialize json from poller")
                    except RuntimeError:
                        pass
            time.sleep(self._config["pollerIntervalS"])
        return poll_for_updates
    
    def attachPoller(self, host: str, port: int, name: str = "") -> uuid.UUID:
        """attachSubscriber opens a new server and lets other servers subscribe (request) the data.

        Args:
            host (str): host that should be subscribed
            port (int): port that should be subscribed
            name (str, optional): name of the dmu element that should be subscribed (Subelements are not supported). Defaults to "".
        """

        if name != "" and not self.dmuObj.elmExists(name):
            self.__log.error("Element %s does not exist", name)
            raise ValueError("dmu does not exist")
        
        subUUID = uuid.uuid1()
        
        if subUUID in self._pollers:
            self.__log.error("Duplicate uuid.")
            raise ValueError("duplicate uuid")
        with self._pollerLock:
            self._pollers.update({subUUID: {"port": port, "host":host, "dmuElm": name}})
        
        #start subscriber thread if not already.
        self._pollerTimer.start()
        return subUUID
    

    def detachPoller(self, uuid: uuid.UUID, name = "") -> bool: 
        """Detaches a subscriber from the element

        Args:
            uuid (uuid.UUID): uuid of the subscriber
            name (str, optional): name of the element the subscriber points to. Defaults to "".

        Returns:
            bool: True if successful
        """

        with self._pollerLock:
            if str(uuid) not in self._pollers:
                self.__log.error("Subscriber does not exist")
                return False
            del self._pollers[uuid]
            
            if len(self._pollers) == 0:
                self._pollerTimer.stop()
        return True
    
    
    def __subscriberFunction(self, httpd: HTTPServer):
        httpd.serve_forever()

    def attachSubscriber(self, host:str, port: int, name: str) -> uuid.UUID:
        """`attachPublisher` opens a new server and lets other servers subscribe (request) the data. 
        
        !!Only one open publisher is allowed for one HttpSrv Publisher as of now. The uuid is for api compatability and reserverd for use later

        Args:
            host (str): hostname of the server (most likley localhost/127.0.0.1/0.0.0.0)
            port (int): the port the webserver will accept connections on
            name (str): Name of the dmu element that will be exposed. Leave empty to expose the whole dmu

        Raises:
            - If another http server is already started it raises a 'ServerAlreadyPublishingException'
            - If the socket (host:port) could not be bound.

        Returns:
            uuid.UUID: UUID of the publisher. Can be used to detach it using `detachPublisher`
        """
        

        self._httpd = HTTPServer((host, port), self.__handler(self.dmuObj, name))
        
        with self._startedLock:
            if self._started:
                raise ServerAlreadyPublishingError()
            self._started = True
            
        # start the server in another thread
        publisherThread = threading.Thread(target=self.__subscriberFunction, args=(self._httpd,))
        publisherThread.start()
        self.__log.debug("added subscriber to %s", name)
            
    def detachSubscriber(self, uuid: uuid.UUID):
        """'detachPublisher' closes the current http server.
            When no server is open this will result in a noop.
            
            This uses http shutdown. This means it will take some time to poll the shutdown signal for the server thread.
        """
        with self._startedLock:
            if not self._started:
                self.__log.warning("http server already stopped")
                return

            self._httpd.shutdown()
        
    def __publisherFunction(self, data, uuid, name, args, context):      
        self.__log.debug("Publishing context: %s", context["globalPublishing"])
        
          
        (host, port) = context["connection"]
        if host == None:
            self.__log.error("host is none")
            return 
        if port == None:
            self.__log.error("port is none")
            return
        
        
        
        conn = HTTPConnection(host, port, timeout=self._config["publisherHTTPTimeoutS"])
        requestURL = f"/{name}"
        pathList = list(args)
        if len(pathList) > 0:
            pathString = "/".join(pathList)
            requestURL += "/" + pathString
        
        body = None
        try:
            body = json.dumps({"data": data})
        except TypeError:
            self.__log.error("could not serialize data")
            return
        
        try:
            conn.request("POST", f"/{name}", body, {
                "Content-Type": "application/json",
            })
            response = conn.getresponse()
        
            if response.status != 200:
                self.__log.error("error during synchronization status code: %s msg: %s", response.status, json.loads(response))
        except TimeoutError:
            self.__log.debug("timout during synchronization. Is the subscriber server up?")
        except Exception as e:
            self.__log.debug("error during synchronization %s", e)
        
    
    def attachPublisher(self, host: str, port: int, name: str) -> uuid.UUID:
        """`attachPublisher` pushes changes made to the element path to the server at host:port.

        Args:
            host (str): The destination hostname
            port (int): The destination port
            name (str): The element to be published once changed. `""` means publishing all changes of the dmu (currently not possible).

        Raises:
            NotImplementedError: Publishing all events of all elements currently not possible. 

        Returns:
            uuid.UUID: The uuid of the publisher
        """
        globalPublishing = name == ""
        context = {
            "connection": (host, port),
            "globalPublishing": globalPublishing
        }
        
        
        if not globalPublishing:     
            eventUUIDStr = self.dmuObj.addElmEvent(self.__publisherFunction, name, context=context)
            self.__log.debug("added publisher to %s", name)
            return uuid.UUID(eventUUIDStr)
        else:
            raise NotImplementedError()
        
    def detachPublisher(self, name: str, uuid: uuid.UUID) -> bool:
        """`detachPublisher` detaches the publishing element event handler from the dmu object.

        Args:
            name (str): The name of the dmu object the publisher listens on. `""` if it's a global publisher
            uuid (uuid.UUID): The uuid of the publisher

        Returns:
            bool: `true` when the detach was successful
        
        Raises:
            `NotImplementedError`: currently global dmu objects are not yet implemented
        """
        
        if name == "":
            raise NotImplementedError
        
        removed = self.dmuObj.rmElmEvent(name, uuid)
        if removed:
            self.__log.debug(f"Removed HTTP Publisher from element {name}")
        else:
            self.__log.warn(f"Unsuccessfull removal of HTTP Publisher from element {name}")
            
        
    def __handler(self, dmuObj: dmu, name: str = ""):
        """internal http handler.

        Args:
            dmuObj (dmu.dmu): The dmu object to act upon
            name (str, optional): The name 

        Returns:
            _type_: _description_
        """
        logger = self.__log
        class reqHandler(BaseHTTPRequestHandler):
            def _send_error(self, code: int, msg: dict[str, str]):
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.send_error(code, json.dumps(msg))
                
            
            def log_message(self, *args ):
                pass

            def do_GET(self):
                """Get has following:
                - /<path> -> returns the data of the element if it exists.
                    If name is empty the whole dmu can be queried
                    If not the name is prefixed to the path
                """
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._send_cors_headers()
                self.end_headers()

                
                
                # get the path
                pathArray = self.path.split("/")
                if len(pathArray) <= 1:
                    self.wfile.write(('{"status":"url_error"}').encode('utf-8'))
                    return

                #if name != "":
                #    pathArray.insert(1,name)
                
                # parse the path
                data = dmuObj.getData(pathArray[1], pathArray[2:])
                
                if data is None:
                    self.wfile.write(('{"status":"not found"}').encode('utf-8'))
                    return
                
                try:
                    self.wfile.write(json.dumps(data).encode())
                except TypeError as e:
                    logger.error("error during serialization: %s", e)
                    self.wfile.write(('{"status":"non_serializable_data_requested"}').encode('utf-8'))
                    return
        
            def do_DELETE(self):
                """Delete has the following:
                - /<path> -> deletes the element at that path if it exists
                """
                def send_success():
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(('{"status":"success"}').encode('utf-8'))
                
                self._send_cors_headers()
                self.send_header('Content-Type', 'application/json')
                
                    
                    
                pathArray = self.path.split("/")
                if len(pathArray) <= 1:
                    self.wfile.write(('{"status":"url_error"}').encode('utf-8'))
                    return
                
                if len(pathArray) == 1:
                    dmuObj.rm(pathArray[1])
                    send_success()
                    return 
                    
                element = dmuObj.getData(pathArray[1], pathArray[2:-2])
                
                if element == None:
                    self._send_error(404, {"status": "not found"})
                    return
                
                if type(element) == list:
                    try:
                        index = int(pathArray[-1])
                        del element[index]
                        send_success()
                        return
                        
                    except ValueError:
                        #last path is not an index
                        self._send_error(400, {"status": "element inside list and last path element was not an index"})
                        return 
                    except Exception as ex:
                        #something else
                        logger.error("exception during list element deletion %s", ex)
                        self._send_error(500, {"status": "something was wrong"})
                        return
                if type(element) == dict:
                    if pathArray[-1] not in element:
                        logger.error("tried deleting non existing subelement")
                        self._send_error(400, {"status": "element inside dict and last path element was not found"})
                        return
                    
                    del element[pathArray[-1]]
                    send_success()
                    return
                
                logger.error("tried removing element from non container parent")
                self._send_error(400, {"status": "element not inside a dict or list"})
                
                    
                
            def do_PUT(self):
                """Put has the following:
                - /<path> -> puts the data into the element if it exists but throws if path element does not exist
                """

                # parse the path and data
                content_length = int(self.headers['Content-Length'])
                if content_length == 0:    
                    logger.warning("No data element in content")
                    self._send_error(411, {"status": "content length required"})
                    return
                
                pathArray = self.path.split("/")


                #if name != "":
                #    pathArray.insert(1,name)
                
                body = self.rfile.read(content_length)
                
                try:
                    body_content = json.loads(body)
                    
                    #error case no data provided    
                    if not "data" in body_content:
                        logger.warning("No data element in content")
                        self._send_error(400, {"status": "no_data"})
                        return
                    
                    #error case element does not exist => create it
                    if not dmuObj.elmExists(pathArray[1]):
                        logger.warning("path does not exist")
                        self._send_error(404, {"status": "element_does_not_exists"})
                        return
                        
                    #set data
                    success = dmuObj.setData(body_content["data"], pathArray)
                    if not success:
                        logger.warning("Data could not be set %s", pathArray[0])
                        self._send_error(500, {"status": "data_set_error"})
                        return
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(('{"status":"success"}').encode('utf-8'))
                        
                except:
                    logger.error("encountered exception during json decode and setData")
                    self._send_error(400, {"status": "json_data_invalid"})
                    return

            def do_POST(self):
                """Posts new data to the element
                - /<path> -> puts the data into the element if it does not exist
                """
                
                
                content_length = int(self.headers['Content-Length'])
                if content_length == 0:    
                    logger.warning("No data element in content")
                    self._send_error(411, {"status": "content length required"})
                    return
                
                pathArray = self.path.removeprefix("/").split("/")
                
                body = self.rfile.read(content_length)
                
                try:
                    body_content = json.loads(body)
                
                    logger.debug("path: %s, data %s", pathArray, body_content)

                    #error case no data provided    
                    if not "data" in body_content:
                        logger.warning("No data element in content")
                        self._send_error(400, {"status": "no_data"})
                        return
                    
                    #error case element does not exist => create it
                    if not dmuObj.elmExists(pathArray[0]):
                        dmuObj.addElm(pathArray[0],None)
                        
                        
                    #set data
                    success = dmuObj.setData(body_content["data"], pathArray)
                    if not success:
                        logger.warning("Data could not be set %s", pathArray[0])
                        self._send_error(400, {"status": "data_set_error"})
                        return
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(('{"status":"success"}').encode('utf-8'))
                        
                except Exception as e:
                    logger.error("encountered exception during json decode and setData: %s", e)
                    self._send_error(400, {"status": "json_data_invalid"})
                    return
            
            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors_headers()
                self.send_header("Access-Control-Allow-Headers", "accept, Content-Type")
                self.end_headers()

            def _send_cors_headers(self):
                """ Sets headers required for CORS """
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "x-api-key,Content-Type")
                
        return reqHandler

