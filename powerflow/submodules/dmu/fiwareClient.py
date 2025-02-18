# Copyright (c) 2022 Manuel Pitz, RWTH Aachen University
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT>, at your option. This file may not be
# copied, modified, or distributed except according to those terms.

import base64
import copy
import datetime
import logging
import numbers
import time
from collections.abc import Iterable
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from filip.clients.ngsi_v2.cb import ContextBrokerClient
from filip.models.base import FiwareHeader
from filip.models.ngsi_v2.context import ContextEntity
from filip.models.ngsi_v2.subscriptions import Subscription

from dmu.dmu import dmu
from dmu.httpSrv import httpSrv

simpleData = {"type": "simpleData", "data": 0}

basicModel = {
    "id": "",
    "lastUpdated": {"type": "Float", "value": 0},
}

publisherStruct = {"entityId": None, "name": "", "dataModel": ""}

subscriberStruct = {
    "entityId": None,
    "name": "",
    "subelements": [],
    "subscriptionId": "",
    "dataModel": "",
}

# XXX only base types maybe use types from filip.models.base
py_to_fi_types = {
    datetime.time: "Time",
    int: "Number",
    float: "Number",
    str: "Text",
    dict: "StructuredValue",
    datetime.date: "Date",
    datetime.datetime: "DateTime",
}


def number_to_py(num: str) -> Union[int, float]:
    if not isinstance(num, str):
        return num
    if "." in num:
        return float(num)
    return int(num)


fi_to_pi_types = {
    "Time": datetime.time.fromisoformat,
    "Number": number_to_py,
    "Integer": int,
    "Float": float,
    "Text": str,
    "StructuredValue": dict,
    "Date": datetime.date.fromisoformat,
    "DateTime": datetime.datetime.fromisoformat,
}


def convert_fi_to_pi(data: Dict[str, str]):
    if "type" in data and data["type"] in fi_to_pi_types:
        return fi_to_pi_types[data["type"]](data["value"])
    return data["value"]


class fiwareClient:
    def __init__(self, dmuObj: dmu, conf):
        self._log = logging.getLogger(__name__)

        self._publisherMap = {}

        self.validateConf(conf)
        """ Create dmu object """
        self._dmuObj = dmuObj

        self._dmuObjPublic = dmu()  # Create a local instance to interface with htttp server

        self._publisherToUuid = {}

        self._publishers = {}
        self._subscribers = {}

        """ Start http server """
        self._httpSrvObj = httpSrv(self._dmuObjPublic, {})
        self._httpSrvObj.attachSubscriber(conf["subscriptionListener"], conf.get("subscriptionListenerPort", conf["subscriptionPort"]), "")

        self._conf = conf

        """ Connect to Fiware """
        self.connectFiware(auth=(conf.get("user"), conf.get("password")))

    def cleanup(self):
        self._log.info("Shutdown fiware connection")

        publisherList = []
        for uuid in self._publishers:
            publisherList.append(uuid)
        for uuid in publisherList:
            self.detachPublisher(self._publishers[uuid]["name"], uuid)

        subsciberList = []
        for uuid in self._subscribers:
            subsciberList.append(uuid)
        for uuid in subsciberList:
            self.detachSubscriber(self._subscribers[uuid]["name"], uuid)

        self._httpSrvObj.cleanup()

        # del self._dmuObjPublic

    def connectFiware(self, auth: Tuple[str,str] = (None,None)):
        """
        This function attaches igreta_io to a fiware instance
        """

        tmpLogger = logging.getLogger("filip")
        tmpLogger.setLevel("WARNING")
        tmpLogger = logging.getLogger("urllib3")
        tmpLogger.setLevel("INFO")
        auth_header = {}
        if auth[0] or auth[1]:
            auth_header = {"Authorization":f"Basic {base64.b64encode(f'{auth[0]}:{auth[1]}'.encode()).decode()}"}
        url = self._conf["protocol"] + "://" + self._conf["fiwareHost"] + ":" + str(self._conf["fiwarePort"])
        if "service" in self._conf:
            fiware_header = FiwareHeader(
                service=self._conf["service"]["name"],
                service_path=self._conf["service"]["path"],
            )
            self._fwObj = ContextBrokerClient(url=url, fiware_header=fiware_header, headers=auth_header)
        else:
            self._fwObj = ContextBrokerClient(url=url, headers=auth_header)

    def handleReceiver(self, data, uuid, name, args, context):
        """
        This function handles new data incoming from fiware and trasnlates it to the igreta_io data structures
        """
        if self._subscribers[uuid]["dataModel"]["type"] == "simpleData":
            if len(self._subscribers[uuid]["subelements"]) > 0:
                self._dmuObj.setDataQueue(
                    convert_fi_to_pi(data[0]["data"]),
                    self._subscribers[uuid]["name"],
                    self._subscribers[uuid]["subelements"],
                )
            else:
                self._dmuObj.setDataQueue(convert_fi_to_pi(data[0]["data"]), self._subscribers[uuid]["name"])
        elif isinstance(data[0], Iterable):
            dataObj = copy.deepcopy(self._subscribers[uuid]["dataModel"])
            # this function only maps elements from the local data model to the local copy of the entity
            for key in dataObj:
                if not key in data[0]:
                    self._log.warning(
                        "Could not find %s in subscribed entity %s. Check entity or model!",
                        key,
                        self._subscribers[uuid]["entityId"],
                    )
                    continue
                if key == "type":
                    continue
                if data[0][key]["value"] is None:
                    continue
                dataObj[key] = convert_fi_to_pi(data[0][key])

            # here we overwrite the local structure with the model based structure!! any local changes are overwritten
            self._dmuObj.setDataQueue(dataObj, self._subscribers[uuid]["name"])

    def handlePublish(self, data, uuid, name, args, context):
        """
        This function handles publishing events
        """

        if not uuid in self._publishers:
            self._log.warning("UUID %s does not exist. Publisher not executed!", uuid)
            return -1

        if len(self._fwObj.get_entity_list(entity_ids=[self._publishers[uuid]["entityId"]])) == 0:
            self._log.warning("Can't write to %s!! Entity does not exist!", self._publishers[uuid]["entityId"])
            return -1

        if self._publishers[uuid]["dataModel"]["type"] == "simpleData":
            self._fwObj.update_attribute_value(
                entity_id=self._publishers[uuid]["entityId"],
                attr_name="data",
                value=data,
            )
        elif isinstance(data, Iterable):
            for key, value in data.items():
                if key == "type":
                    continue
                self._fwObj.update_attribute_value(
                    entity_id=self._publishers[uuid]["entityId"],
                    attr_name=key,
                    value=value,
                )
        else:
            self._log.warning(
                "Provided data for entity %s could not be handled. Check data content!",
                self._publishers[uuid]["entityId"],
            )

        self._fwObj.update_attribute_value(
            entity_id=self._publishers[uuid]["entityId"],
            attr_name="lastUpdated",
            value=time.time(),
        )

    def createEntity(self, entityId, model=simpleData, remap=True, infer_type=False):
        """
        This function can create new entities.
        with model a data model can be provides
        with remap the datamodel is mapped to fiware datamodel.
        if remap is true infer
        """
        model = copy.deepcopy(model)

        # sanity check
        if not type(model) is dict:
            self._log.warning("Data model must be of type dict")
            return False
        if "type" not in model:
            self._log.warning("Missing key 'type' in model. Entity %s not created", entityId)
            return False
        if "lastUpdated" in model:
            self._log.warning("'lastUpdated' conflicts with an existing key. Please remove from model")
            return False
        if "id" in model:
            self._log.warning("'id' conflicts with an existing key. Please remove from model")
            return False

        if not remap:
            for key in model:
                if key == "type":
                    continue

                # if not "value" in model[key]:
                #     self._log.warning(
                #         "Data model not valid. Value key in %s missing", key
                #     )
                #     return False
                if not isinstance(model[key]["value"], (numbers.Number, str, list, dict)):
                    self._log.warning(
                        "Only numbers, string or list allowed but %s is used for %s",
                        type(model[key]["value"]),
                        key,
                    )
                    return False
        else:
            model = self.remapData(model, infer_type)

        model.update(basicModel)

        model["id"] = entityId

        entityContext = ContextEntity(**model)  # @todo check if fiware broker is running
        if len(self._fwObj.get_entity_list(entity_ids=[entityId])) == 0:
            if self._fwObj.post_entity(entity=entityContext):
                return True
        else:
            self._log.warning("Entity with entity_id %s already exists", entityId)

        return False

    def entityExists(self, entityId):
        """
        Check if entity exists on broaker
        """
        if len(self._fwObj.get_entity_list(entity_ids=[entityId])) != 0:
            return True
        else:
            return False

    def remapData(self, src, infer_type=False):
        """
        This function remaps a simplified data model to be compatible with fiware
        """
        tmpModel = {}
        for key in src:
            if key == "type":
                tmpModel.update({key: src[key]})
                continue
            if not isinstance(src[key], (numbers.Number, str, list, dict)):
                self._log.warning(
                    "Only numbers, string or list allowed but %s is used for %s",
                    type(src[key]),
                    key,
                )
                return False
            tmpModel.update({key: {"value": src[key]}})
            if infer_type:
                tmpModel[key].update({"type": py_to_fi_types[type(src[key])]})

        return tmpModel

    def deleteEntity(self, entityId, model=simpleData):
        if "type" not in model:
            self._log.warning("Can't remove entity. Invalid model!")
            return False

        self._fwObj.delete_entity(entityId, model["type"])
        return True

    def sync(self, name):
        if not name in self._publisherToUuid:
            self._log.error("Publisher for %s not registered. Cannot sync", name)
            return -1

        self._dmuObj.notifyElmEvent(name, self._publisherToUuid[name])

    def attachPublisher(self, entityId, name, dataModel=simpleData):
        """
        This functions enables a publisher via the local storage structure
        Returns -1 in case of an error. Otherwise a uuid
        """

        if name in self._publisherToUuid:
            self._log.warning("Publisher from %s to entity id %s already registered", name, entityId)
            return -1

        uuid = self._dmuObj.addElmEvent(self.handlePublish, name)
        self._publisherToUuid.update({name: uuid})

        if uuid != False:
            if not uuid in self._publishers:
                self._publishers.update({uuid: {}})
                self._publishers[uuid] = copy.deepcopy(publisherStruct)
                self._publishers[uuid]["entityId"] = entityId
                self._publishers[uuid]["name"] = name
                self._publishers[uuid]["dataModel"] = dataModel
            else:
                self._log.error("Duplicate uuid. This really should not happen. %s", uuid)
                return -1

        return uuid

    def detachPublisher(self, name, uuid):
        """
        This functions detaches a publisher via the local storage structure
        """
        if not uuid in self._publishers:
            self._log.warning("Can't detach publischer from %s . UUID %s does not exists", name, uuid)
            return False

        self._dmuObj.rmElmEvent(name, uuid)
        del self._publishers[uuid]
        del self._publisherToUuid[name]
        return True

    # XXX should condition just be a string or should this be a list
    def attachSubscriber(
        self,
        entityId: str,
        name: str,
        *args,
        dataModel: Dict[str, Any] = simpleData,
        federtationUrl: str = "",
        expire_in: Optional[str] = None,
        condition: Union[List[str], Literal[False]] = ["lastUpdated"],
    ):
        """
        This function subscribes to entity.
        @todo: currently the subscription expires after 15 minutes. not sure what the expected behaviour is
        Returns -1 in case of an error. Otherwise a 1
        """

        if isinstance(condition, str):
            # if condition is provided directly put it into array here, allows specification of multiple conditions
            condition = [condition]
        if not condition:
            # if condition is falsy (empty list or False or None etc.) notfiy on any change
            condition = []

        args = self.__handleListArguments(*args)

        subKeys = list(dataModel.keys())

        if not self._dmuObj.elmExists(name):
            self._log.warning("DMU element with %s must exists to subscribe. Cannot create subscription!", name)
            return -1

        if not self._dmuObjPublic.elmExists(entityId):
            self._dmuObjPublic.add(dataModel, entityId)  # create local data element to handle subscription

        uuid = self._dmuObjPublic.addElmEvent(self.handleReceiver, entityId)
        if not uuid:
            self._log.error("Duplicate uuid. This really should not happen. %s", uuid)
            self._dmuObjPublic.rm(entityId)
            return -1

        self._subscribers.update({uuid: {}})
        self._subscribers[uuid] = copy.deepcopy(subscriberStruct)
        self._subscribers[uuid]["name"] = name
        self._subscribers[uuid]["subelements"] = ""
        self._subscribers[uuid]["entityId"] = entityId
        self._subscribers[uuid]["dataModel"] = dataModel

        subscriptionUrl = (
            self._conf.get("protocolSubscription","http")+"://" + self._conf["subscriptionHost"] + ":" + str(self._conf["subscriptionPort"]) + "/" + entityId
        )

        if federtationUrl:
            subscriptionUrl = federtationUrl

        subKeys.append("lastUpdated")
        subStruct = {
            "description": "Subscription to receive HTTP-Notifications about " + entityId,
            "subject": {
                "entities": [{"id": entityId}],
                "condition": {"attrs": condition},
            },
            "notification": {  # @todo check what is needed to support https here
                "http": {"url": subscriptionUrl},
                "attrs": subKeys,
            },
            "throttling": 0,
        }
        if expire_in is not None:
            subStruct["expires"] = expire_in

        subObj = Subscription(**subStruct)
        # check if sub already exist and remove it
        subs = self._fwObj.get_subscription_list()

        sub_hash = subObj.json(include={"subject", "notification"})
        for subElm in subs:
            if sub_hash == subElm.json(include={"subject", "notification"}):
                self._fwObj.delete_subscription(subElm.id)
                self._log.warning("Subscription auto removed before reattached")

        # create new subscription
        self._subscribers[uuid]["subscriptionId"] = self._fwObj.post_subscription(subscription=subObj)

        return 1

    def detachSubscriber(self, name, uuid):
        """
        This function removes the subscription to an entitiy
        """
        if not uuid in self._subscribers:
            self._log.warning("Can't detach subscriber from %s . UUID %s does not exists", name, uuid)
            return False
        try:
            self._fwObj.delete_subscription(self._subscribers[uuid]["subscriptionId"])
            self._dmuObjPublic.rm(self._subscribers[uuid]["entityId"])
            del self._subscribers[uuid]
        except:
            self._log.warning("Could not remove subscription with id %s ", self._subscribers[uuid]["subscriptionId"])
            self._dmuObjPublic.rm(self._subscribers[uuid]["entityId"])
            del self._subscribers[uuid]
            return False

        return True

    def validateConf(self, conf):
        """
        This function validates the configuration.
        """

        keyCheck = [
            "fiwareHost",
            "fiwarePort",
            "subscriptionHost",
            "subscriptionListener",
            "subscriptionPort",
            "protocol",
        ]
        for val in keyCheck:
            if not val in conf:
                raise Exception("Key missing in config. Please add " + val)

    def __handleListArguments(self, *args):
        """handles cases of lists and values as arguements"""

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
