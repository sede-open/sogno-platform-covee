# Copyright (c) 2020 Manuel Pitz, RWTH Aachen University
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT>, at your option. This file may not be
# copied, modified, or distributed except according to those terms.

import paho.mqtt.client as mqtt
import logging, copy, json, uuid
import sys

publisherStruct = {
    "topic" : None,
    "formatPtr" : None
}

subscriberStruct = {
    "topic" : None,
    "formatPtr" : None,
    "name" : "",
    "subelements" : []
}

class MqttClient:
    def __init__(self, host, dmuObj, port=1883, user="", password="", cert="", ver=None, tls_insecure=True, keepalive=5):
        self._log = logging.getLogger(__name__)
        
        try:
            self._mqttHandle = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        except:
            self._log.error("Could not connect to mqtt server")
            sys.exit(0)

        if user != "":
            self._mqttHandle.username_pw_set(username=user,password=password)
            
        if cert != "":
            try:
                self._mqttHandle.tls_set(cert, tls_version=ver)
            except:
                self._log.error("Could not set tls")
            self._mqttHandle.tls_insecure_set(tls_insecure)

        self._log.warning("Connect to %s:%s@%s:%i",user, password, host, port)

        self._mqttHandle.on_connect = self.on_connect
        self._mqttHandle.on_disconnect = self.on_disconnect
        self._mqttHandle.on_message = self.on_message
        self._mqttHandle.connect(host, port, keepalive)
        self._mqttHandle.loop_start()

        self._dmuObj = dmuObj
        self._publisherParameters = {}

        self._subscribedTopics = {}
    
    def on_connect(self, client, userdata, flags, rc):
        ''' on_connect callback '''
        self._log.info("MQTT connected with result code " + str(rc))
        self._mqttHandle._connected = True # XXX accessing _methods should be avoided when ever possible

    def on_disconnect(self, client, userdata, rc): 
        ''' on_disconnect callback '''
        self._log.info("MQTT disconnected")
        self._mqttHandle._connected = False # XXX accessing _methods should be avoided when ever possible

    def on_message(self, client, userdata, message):
        for uuidStr in self._subscribedTopics:
            elm = self._subscribedTopics[uuidStr]
            if elm["topic"] == message.topic:
                data = elm["formatPtr"]("decode", message.payload)
                self._dmuObj.setDataSubset(data, elm["name"], elm["subelements"])

    def autoAttachSubscriber(self, name, *args):
        '''
        This is a simplified alias for attachSubscriber. 
        This functions assumes to autgenerate the topic and to use json as default
        '''
        topic = "/" + name
        if len(args):
            topic = topic + "/" + "/".join(args)
        self.attachSubscriber(topic, "json", name, *args)

    def attachSubscriber(self, topic, formatIn, name, *args):
        ''' This function subscribes to a topic and creates the connection to the dmu '''


        args = self.__handleListArguments(*args)

        if not self._dmuObj.elmExists(name,args):
            logging.warn("One or more element do not exist %s->%s",name, '->'.join(args))
            return False

        uuidStr = str(uuid.uuid1())

        if not uuidStr in self._subscribedTopics:
            self._subscribedTopics[uuidStr] = copy.deepcopy(subscriberStruct)
            self._subscribedTopics[uuidStr]["subelements"] = copy.deepcopy(args)
            self._subscribedTopics[uuidStr]["name"] = name
            self._subscribedTopics[uuidStr]["topic"] = topic
            if formatIn == "json":
                self._subscribedTopics[uuidStr]["formatPtr"] = self.jsonHandler
            elif formatIn == "json-villas":
                self._subscribedTopics[uuidStr]["formatPtr"] = self.jsonHandler_Villas
            else:#default to json
                self._subscribedTopics[uuidStr]["formatPtr"] = self.jsonHandler
            self._mqttHandle.subscribe(topic)
        else:
            self._log.error("Dublicate uuid in _subscribedTopics. This really should not happen. %s", uuidStr)

        
    def handlePublishMqtt(self, data, uuid, name, args, context):
        dataToPublish = self._publisherParameters[uuid]["formatPtr"]("encode", data)

        self._mqttHandle.publish(self._publisherParameters[uuid]["topic"], dataToPublish)

    def jsonHandler_Villas(self, direction, data):
        if direction == "encode":
            return json.dumps([data]).encode('utf-8')
        elif direction == "decode":
            jsonData = {}
            try:
                jsonData = json.loads(data.decode('utf-8'))[0]
            except:
                self._log.error("Json data invalid")
                
            return jsonData
        else:
            self._log.warning("Dircetion not recognized: %s", direction)    

    def jsonHandler(self, direction, data):
        if direction == "encode":
            return json.dumps(data).encode('utf-8')
        elif direction == "decode":
            jsonData = {}
            try:
                jsonData = json.loads(data.decode('utf-8'))
            except:
                self._log.error("Json data invalid")
                
            return jsonData
        else:
            self._log.warning("Dircetion not recognized: %s", direction)


    def autoAttachPublisher(self, name, *args):
        '''
        This is a simplified alias for attachPublischer. 
        This functions assumes to autgenerate the topic and to use json as default
        '''

        topic = "/" + name
        if len(args):
            topic = topic + "/" + "/".join(args)

        self.attachPublisher(topic, "json", name, *args)

    def attachPublisher(self, topic, formatIn, name,  *args):
        '''
        This function connect a dmu element with the mqtt tx and handles the registration
        @param format: json
        @param topic: None means the topic 
        '''

        args = self.__handleListArguments(*args)


        uuid = self._dmuObj.addElmEvent(self.handlePublishMqtt, name, args)
        if uuid != False:
            if not uuid in self._publisherParameters:
                self._publisherParameters.update({uuid : {}})
                self._publisherParameters[uuid] = copy.deepcopy(publisherStruct)
                self._publisherParameters[uuid]["topic"] = topic
                if formatIn == "json":
                    self._publisherParameters[uuid]["formatPtr"] = self.jsonHandler
                elif formatIn == "json-villas":
                    self._publisherParameters[uuid]["formatPtr"] = self.jsonHandler_Villas
                else:#default to json
                    self._publisherParameters[uuid]["formatPtr"] = self.jsonHandler
            else:
                self._log.error("Dublicate uuid. This really should not happen. %s", uuid)
        else:
            self._log.warning("could not add event listener to %s->%s",  name, '->'.join(args))

        return False

    
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
        
mqttClient = MqttClient
    
        