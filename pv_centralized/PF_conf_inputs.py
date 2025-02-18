import numpy as np 
import time
import sys
import requests
import json
import csv

reqData = {
    "data": {
        "nodes": [4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,31,32]
    }
}

headers = {'content-type': 'application/json'}
try:
    jsonData = (json.dumps(reqData)).encode("utf-8")
except:
    logging.warn("Malformed json")
result = requests.post("http://pv_centralized:7071/set/nodes/data_nodes/", data=jsonData, headers=headers)
