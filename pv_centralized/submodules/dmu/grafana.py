from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import time
from typing import Any
from dmu import dmu
import threading

class Grafana:
    """A HTTP Grafana endpoint provider.
        Using attachPublisher / detachPublisher a element or all elements can be published to be visualized by Grafana.
    """
    def __init__(self, dmuObj: dmu.dmu, host: str, port: int):
        self.__log = logging.getLogger(__name__)
        self.__log.setLevel(logging.WARNING)
    
        self.dmuObj = dmuObj
        self._httpd: HTTPServer | None = None
        logging.getLogger('httpd-ken').setLevel(logging.ERROR)

        self._startedLock = threading.Lock()
        self.host = host
        self.port = port
        
    def __del__(self):
        self.cleanup()
        
    def cleanup(self):
        """`cleanup` detaches the publisher. Acts as a proxy to detachPublisher
        """
        self.detachPublisher()
           
    def __subscriberFunction(self, httpd: HTTPServer):
        httpd.serve_forever()
        
    def attachPublisher(self):
        """`attachPublisher` opens the http endpoint for Grafana
        """
        with self._startedLock:
            if self._httpd == None:
                # No two parallel servers can be started, due to socket binding conflicts
                self._httpd = HTTPServer((self.host, self.port), self.__handler())
                publisherThread = threading.Thread(target=self.__subscriberFunction, args=(self._httpd,))
                publisherThread.start()

    def detachPublisher(self) -> bool:
        """`detachPublisher` closes the http endpoint for Grafana

        Returns:
            bool: `True` if successful. `False` if no server was running
        """
        with self._startedLock:
            if self._httpd is None:
                return False
            self._httpd.shutdown()
        return True
    
    def __handler(self):
        logger = self.__log
        dmuObj = self.dmuObj
        class reqHandler(BaseHTTPRequestHandler):
            def _send_response(self, code: int, status: str, data: Any, raw = False):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self._send_cors_headers()
                self.send_header("Access-Control-Allow-Headers", "accept, Content-Type")
                self.end_headers()
                
                if raw:
                    self.wfile.write(json.dumps(data).encode("utf-8"))
                    return
                self.wfile.write(json.dumps({"status": status, "data": data}).encode("utf-8"))
                
                
            def _send_cors_headers(self):
                """ Sets headers required for CORS """
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "x-api-key,Content-Type")
                
            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self._send_cors_headers()
                self.send_header("Access-Control-Allow-Headers", "accept, Content-Type")
                self.end_headers()

            def do_GET(self):
                self.send_response_only(200, "OK")
                self.end_headers()

            def do_POST(self):
                pathArray = self.path.split("/")
                if len(pathArray) <= 1:
                    self.wfile.write(('{"status":"url_error"}').encode('utf-8'))
                    return
                
                #pathArray[0] == "grafana":#Grafana interface
                if pathArray[1] == "search":#Grafana search
                    elements = dmuObj.getAllElementNames()
                    self._send_response(200, "success", elements, True)
                    return
                
                
                content_length = int(self.headers['Content-Length'])
                if content_length == 0:    
                    #logger.warning("No data element in content")
                    self._send_response(411, "", {"status": "content length required"}, True)
                    return
                
                body = self.rfile.read(content_length)
                
                try:
                    body_content = json.loads(body)
                    if pathArray[1] == "query":
                        dataArray = []
                        tempTimestamp = time.time()*1000 #used to timetag single values
                        for target in body_content["targets"]:
                            if not "target" in target: # ignore first queries
                                continue
                            elmName = target["target"]
                            logger.debug("Name: %s", elmName)
                            elmList = elmName.split("/")
                            if not dmuObj.elmExists(elmList[0],elmList[1:]):
                                #add empty element to make client happy if non existig element is queried
                                dataArray.append({"target": elmList[-1], "datapoints" : []})
                                logger.warning("Element does not exist %s", elmName)
                                
                                continue
                            try:
                                outputData = dmuObj.getData(elmList[0], elmList[1:])
                                if isinstance(outputData, list):
                                    if len(outputData)>1:
                                        dataArray.append({"target": elmList[-1], "datapoints" : sorted(outputData, key = lambda x: x[1])})
                                    else:
                                        dataArray.append({"target": elmList[-1], "datapoints" : [outputData]})
                                else:
                                    dataArray.append({"target": elmList[-1], "datapoints" : [[outputData,tempTimestamp]]})
                            except TypeError:
                                dataArray.append({"target": elmList[-1], "datapoints" : []})#add empty element to make client happy if non existig element is queried
                                logger.warning("Requests data that was not JSON serializable")
                        self._send_response(200, "ok", dataArray, True)
                    else:
                        self._send_response(500, "", "grafana_url_error", True)
                        logger.warning("Unknown url %s", pathArray[1])
                except Exception as e:
                    logger.error("encountered exception during json decode and data append %s", e)
                    self._send_response(400, "", {"status": "json_data_invalid"}, True)
                    
        return reqHandler