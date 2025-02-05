import numpy as np 
import os
import coloredlogs, logging, threading
import time
import json
from importlib import import_module
from alive_progress import alive_bar
from pypower.api import *
from pypower.ext2int import ext2int
import covee.control_strategies.utils as utils
from covee.powerflow.runPF_class import runPF_class
from covee.csv_files.save_results import save_results


'''
coloredlogs.install(level='DEBUG',
fmt='%(asctime)s %(levelname)-8s %(name)s[%(process)d] %(message)s',
field_styles=dict(
    asctime=dict(color='green'),
    hostname=dict(color='magenta'),
    levelname=dict(color='white', bold=True),
    programname=dict(color='cyan'),
    name=dict(color='blue')))
'''
logging.basicConfig(level = logging.INFO)
logging.info("Program Start")   ##########

# Read json file and set Control Strategy and Case 
# =====================================================================================================
with open("./examples/conf.json", "r") as f:
    conf_dict = json.load(f)

module_obj = utils.select(conf_dict)
Quadratic_Control = module_obj.select_control()
case = module_obj.select_case()
logging.info('\'Quadratic_Control\' and \'case\' now refer to specific Python modules.')
# =====================================================================================================

'''
#########################################################################################################
##################################### INITIALIZE ########################################################
#########################################################################################################
'''
# Get the grid data infos
# =====================================================================================================
additional = utils.additional() 

logging.info('\'additional\' is an additional Class object')

conf_dict = additional.convert_index(conf_dict)
active_nodes = conf_dict["CONTROL_DATA"]["active_nodes"]   # number of active DGs
active_ESS = conf_dict["CONTROL_DATA"]["active_ESS"]       # number of active ESSs
logging.info('1 subtracted form all active_nodes and active_ESS')
logging.info("active_nodes"+str(active_nodes))

ppc_obj = case.case_()
logging.info('ppc_obj is a case_ object')
ppc = ppc_obj.case()
ppc = ext2int(ppc)      # convert to continuous indexing starting from 0
logging.info('ppc contains all the case-related information')
BUS_TYPE = 1
[grid_data,reactive_power,active_power,active_power_ESS] = additional.system_info(ppc,BUS_TYPE, active_nodes, active_ESS)

logging.info('\'grid_data\', \'reactive_power\', \'active_power\', \'active_power_ESS\' arrays and \'additional\' object are activated.')

# Initialize the control
# =====================================================================================================
control = Quadratic_Control.Quadratic_Control(grid_data, active_nodes ,active_ESS, conf_dict["CONTROL_DATA"])
logging.info('\'control\' object is created')
[R,X,output] = control.initialize_control()
save_obj = save_results(voltage_list = [], iterations = [], conf_dict = conf_dict)

# Initialize the powerflow
# =====================================================================================================
run_PF = runPF_class(active_nodes, active_ESS, grid_data["full_nodes"], grid_data["total_control_nodes"])
profiles = run_PF.read_profiles(conf_dict, grid_data)
active_power_dict = {}
reactive_power_dict = {}
active_power_ESS_dict = {}

'''
#########################################################################################################
############################################ RUN ########################################################
#########################################################################################################
'''
with alive_bar(int(len(profiles["gen_profile"]))) as bar:  # declare your expected total
    for iter in range(int(len(profiles["gen_profile"]))):

        ################################# Run the PowerFlow #####################################
        #########################################################################################
        [v_tot,v_gen,p,c,p_load,v_pv,v_ess] = run_PF.run_Power_Flow(ppc,output["DG"]["active_power"],output["DG"]["reactive_power"],output["ESS"]["active_power"],profiles["gen_profile"][iter],profiles["load_profile"][iter])

        
        ###################### Calculate the control output #####################################
        #########################################################################################
        output = control.control_(profiles["gen_profile"][iter][active_nodes], output, R, X, v_gen, v_ess, VMIN=conf_dict["CONTROL_DATA"]["VMIN"], VMAX=conf_dict["CONTROL_DATA"]["VMAX"], iter=iter)

        # update the dictionaries
        #########################################################################################
        [reactive_power_dict, active_power_dict, active_power_ESS_dict] = additional.update_dict(output, reactive_power_dict, active_power_dict, active_power_ESS_dict)      
        save_obj.save_list(output, v_tot, iter)

        #print("voltage ", v_tot)
        #print("pv_input ", profiles["gen_profile"][iter][active_nodes])
        #print("reactive_power_dict ", reactive_power_dict)
        
        bar()

    # Save the data in csv files
    # =====================================================================================================
    save_obj.save_csv()
    # Plot function
    # =====================================================================================================
    save_obj.Plot("voltage", {"VMAX" : conf_dict["CONTROL_DATA"]["VMAX"],
                        "VMIN" : conf_dict["CONTROL_DATA"]["VMIN"]})
    for i in conf_dict["CONTROL_DATA"]["control_variables"]["DG"]:
        save_obj.Plot(i+'_DG', None)
    for i in conf_dict["CONTROL_DATA"]["control_variables"]["ESS"]:
        save_obj.Plot(i+"_ESS", None)

    logging.info('simulation finished')


          