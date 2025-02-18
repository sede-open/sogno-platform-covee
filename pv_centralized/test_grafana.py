import csv
import os
import numpy as np

import coloredlogs, logging, threading
from threading import Thread
from submodules.dmu.dmu import dmu
from submodules.dmu.httpSrv import httpSrv
import time

############################ Start the Server #######################################################

coloredlogs.install(level='DEBUG',
fmt='%(asctime)s %(levelname)-8s %(name)s[%(process)d] %(message)s',
field_styles=dict(
    asctime=dict(color='green'),
    hostname=dict(color='magenta'),
    levelname=dict(color='white', bold=True),
    programname=dict(color='cyan'),
    name=dict(color='blue')))
logging.info("Program Start")

''' Initialize objects '''
dmuObj = dmu()

''' Start http server '''
httpSrvThread = threading.Thread(name='httpSrv',target=httpSrv, args=("0.0.0.0", 8080,dmuObj,))
httpSrvThread.start()
#######################################################################################################


########################################################################################################
#########################  Section for Posting Signal (for Grafana) ####################################
########################################################################################################
grafanaArrayPos = 0
dataDict = []
for i in range(10000):
    dataDict.extend([[0,0]])

dmuObj.addElm("grafana test", dataDict)

k = 0
try:
    while True:
        # for k in range(1000):

        ts = int(round(time.time() * 1000.0))
        point = np.sin(10*float(k))
        sim_list = [point,ts]
        dmuObj.setDataSubset(sim_list,"grafana test",grafanaArrayPos)

        grafanaArrayPos = grafanaArrayPos+1
        if grafanaArrayPos>10000:
            grafanaArrayPos = 0
        time.sleep(0.1)
        k+=1

    print('simulation finished')

except (KeyboardInterrupt, SystemExit):

    print('simulation finished')
