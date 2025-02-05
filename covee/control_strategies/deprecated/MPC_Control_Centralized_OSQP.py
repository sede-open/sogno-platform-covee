import numpy as np
from cvxopt import matrix, solvers
import matplotlib.pyplot as plt
from scipy.linalg import block_diag
import os
import osqp
from scipy import sparse
import time
import coloredlogs, logging, threading

import control_strategies.model_predictive_control as quadratic_control


class MPC_Control():

    def __init__(self, grid_data, num_pv,num_ESS,full_nodes):
        self.grid_data = grid_data	
        self.num_pv = num_pv
        self.num_bus = self.grid_data["nb"]
        self.full_nodes = full_nodes     


        self.QMIN = []
        self.QMAX = []
        self.PMIN = []
        self.PMAX = []

        # Problem parameters
        # =============================================================
        self.V_MIN = 0.95  # undervoltage limit
        self.V_MAX = 1.05  # overvoltage limit
        self.V_NOM = 1.00  # nominal voltage

        # DEFINE LIM
        # =============================================================
        for i in range(int(len(self.num_pv))):
            self.QMIN.append(-0.8)
            self.QMAX.append(0.8)
            self.PMIN.append(-3.0)
            self.PMAX.append(+3.0)

    def initialize_control(self): 

        self.bus_values = self.full_nodes[1:]
        self.P_activate = [1e6]*len(self.bus_values)


    def control_(self, resize, forecast, pvproduction, active_power, reactive_power,active_power_ess, R, X, R_ess, active_nodes, v_tot, VMAX, reference, activation_nodes, predictions, variables, iteration, SoC_meas, SoC_ref, activate_SoC, modify_obj_function):

        if resize == "yes":
            full_nodes = self.bus_values
        else:
            full_nodes = self.full_nodes

        n = len(full_nodes)
        pred = predictions
        additional = quadratic_control.additional(full_nodes)

        n_PV = np.shape(X)[0]
        n_ess = np.shape(R_ess)[0]

        pv_input_full = {"pred_"+str(s+1): None for s in range(pred)}
        activation_nodes_full = {"pred_"+str(s+1): None for s in range(pred)}
        q_ref_values = {"pred_"+str(s+1): None for s in range(pred)}
        q_ref = {"pred_"+str(s+1): None for s in range(pred)}
        p_ref = {"pred_"+str(s+1): None for s in range(pred)}
        p_ess_ref = {"pred_"+str(s+1): None for s in range(pred)}
        reactive_power_full = {"pred_"+str(s+1): None for s in range(pred)}
        active_power_full = {"pred_"+str(s+1): None for s in range(pred)}
        active_power_ess_full = {"pred_"+str(s+1): None for s in range(pred)}
        SoC_full = {"pred_"+str(s+1): None for s in range(pred)}
        v_tot_dict = {"active_power": {"pred_"+str(s+1): None for s in range(pred)}, "reactive_power": {"pred_"+str(s+1): None for s in range(pred)}, "active_power_ess": {"pred_"+str(s+1): None for s in range(pred)}}

        reactive_power_sol = {"pred_"+str(s+1): None for s in range(pred)}
        active_power_sol = {"pred_"+str(s+1): None for s in range(pred)}
        active_power_ess_sol = {"pred_"+str(s+1): None for s in range(pred)}

        reference_reactive_power_full = {"pred_"+str(s+1): None for s in range(pred)}
        reference_active_power_full = {"pred_"+str(s+1): None for s in range(pred)}
        reference_active_power_ess_full = {"pred_"+str(s+1): None for s in range(pred)}
        reference_voltage_full = {"pred_"+str(s+1): None for s in range(pred)}
        SoC_ref_full = {"pred_"+str(s+1): None for s in range(pred)}

        if resize == "yes":
            for s in range(pred):
                [active_power_full["pred_"+str(s+1)], reactive_power_full["pred_"+str(s+1)], 
                active_power_ess_full["pred_"+str(s+1)], pv_input_full["pred_"+str(s+1)], SoC_full["pred_"+str(s+1)], full_active, 
                activation_nodes_full["pred_"+str(s+1)],reference_active_power_full["pred_"+str(s+1)],
                reference_reactive_power_full["pred_"+str(s+1)],reference_active_power_ess_full["pred_"+str(s+1)], reference_voltage_full["pred_"+str(s+1)],
                SoC_ref_full["pred_"+str(s+1)]] = additional.resize_in(full_nodes,active_nodes,active_power["pred_"+str(s+1)], reactive_power["pred_"+str(s+1)],active_power_ess["pred_"+str(s+1)], SoC_meas["pred_"+str(s+1)],
                                                                        pvproduction["pred_"+str(s+1)],reference["active_power"]["pred_"+str(s+1)],reference["reactive_power"]["pred_"+str(s+1)],
                                                                        reference["active_power_ess"]["pred_"+str(s+1)],reference["voltage"]["pred_"+str(s+1)], SoC_ref["pred_"+str(s+1)],activation_nodes,n)
        else:
            for s in range(pred):
                [active_power_full["pred_"+str(s+1)], reactive_power_full["pred_"+str(s+1)], 
                active_power_ess_full["pred_"+str(s+1)], pv_input_full["pred_"+str(s+1)], SoC_full["pred_"+str(s+1)], full_active, 
                activation_nodes_full["pred_"+str(s+1)],reference_active_power_full["pred_"+str(s+1)],
                reference_reactive_power_full["pred_"+str(s+1)],reference_active_power_ess_full["pred_"+str(s+1)], reference_voltage_full["pred_"+str(s+1)],
                SoC_ref_full["pred_"+str(s+1)]] = [active_power["pred_"+str(s+1)], reactive_power["pred_"+str(s+1)], 
                                                        active_power_ess["pred_"+str(s+1)], pvproduction["pred_"+str(s+1)], SoC_meas["pred_"+str(s+1)], active_nodes, 
                                                        activation_nodes,reference["active_power"]["pred_"+str(s+1)],
                                                        reference["reactive_power"]["pred_"+str(s+1)],reference["active_power_ess"]["pred_"+str(s+1)], reference["voltage"]["pred_"+str(s+1)],
                                                        SoC_ref["pred_"+str(s+1)]]


        if iteration == 0:                                                                                                                                                            
            v_tot_dict = {"active_power": {"pred_"+str(s+1): np.transpose(np.matrix(v_tot)) for s in range(pred)}, "reactive_power": {"pred_"+str(s+1): np.transpose(np.matrix(v_tot)) for s in range(pred)}, "active_power_ess": {"pred_"+str(s+1): np.transpose(np.matrix(v_tot)) for s in range(pred)}}
        else:
            for s in range(pred):
                if s==0:
                    v_tot_dict["active_power"]["pred_"+str(s+1)] = np.transpose(np.matrix(v_tot))
                    v_tot_dict["reactive_power"]["pred_"+str(s+1)] = np.transpose(np.matrix(v_tot))
                    v_tot_dict["active_power_ess"]["pred_"+str(s+1)] = np.transpose(np.matrix(v_tot))
                else:
                    v_tot_dict["active_power"]["pred_"+str(s+1)] = v_tot_dict["active_power"]["pred_"+str(s)] -R*np.transpose(np.matrix([active_power_full["pred_"+str(s)]]))+R*np.transpose(np.matrix([active_power_full["pred_"+str(s+1)]]))
                    v_tot_dict["reactive_power"]["pred_"+str(s+1)] = v_tot_dict["reactive_power"]["pred_"+str(s)] -X*np.transpose(np.matrix(reactive_power_full["pred_"+str(s)]))+X*np.transpose(np.matrix(reactive_power_full["pred_"+str(s+1)]))
                    v_tot_dict["active_power_ess"]["pred_"+str(s+1)] = v_tot_dict["active_power_ess"]["pred_"+str(s)] -R_ess*np.transpose(np.matrix([active_power_ess_full["pred_"+str(s)]]))+R_ess*np.transpose(np.matrix([active_power_ess_full["pred_"+str(s+1)]]))

        k = 0
        var= {}
        var["q_sol"] = None
        var["p_sol"] = None
        var["p_ess_sol"] = None
        var["ref"] =  {"active_power": reference_active_power_full,"reactive_power": reference_reactive_power_full,"active_power_ess": reference_active_power_ess_full,"voltage": reference_voltage_full}
        var["QMIN"] = {"pred_"+str(s+1): np.array([-0.312*pv_input_full["pred_"+str(s+1)][i] for i in range(int(n))]) for s in range(pred)}
        var["QMAX"] = {"pred_"+str(s+1): np.array([0.312*pv_input_full["pred_"+str(s+1)][i] for i in range(int(n))]) for s in range(pred)}
        var["PMIN"] = {"pred_"+str(s+1): np.array([-(pv_input_full["pred_"+str(s+1)][i]+1e-6) for i in range(int(n))]) for s in range(pred)}
        var["PMAX"] = {"pred_"+str(s+1): np.array([0.0+1e-6 for i in range(int(n))]) for s in range(pred)}
        var["PMIN_ESS"] = {"pred_"+str(s+1): np.array([-0.3 for i in range(int(n))]) for s in range(pred)}
        var["PMAX_ESS"] = {"pred_"+str(s+1): np.array([0.3 for i in range(int(n))]) for s in range(pred)}
        var["VNOM"] = {"active_power": {"pred_"+str(s+1): v_tot_dict["active_power"]["pred_"+str(s+1)]/(len(variables))-R*np.transpose(np.matrix([active_power_full["pred_"+str(s+1)]]))#-X*np.transpose(np.matrix([reactive_power_full["pred_"+str(s+1)]]))-R_ess*np.transpose(np.matrix([active_power_ess_full["pred_"+str(s+1)]]))                
                                        for s in range(pred)},
                        "reactive_power": {"pred_"+str(s+1): v_tot_dict["reactive_power"]["pred_"+str(s+1)]/(len(variables))-X*np.transpose(np.matrix([reactive_power_full["pred_"+str(s+1)]])) 
                                        for s in range(pred)},
                        "active_power_ess": {"pred_"+str(s+1): v_tot_dict["active_power_ess"]["pred_"+str(s+1)]/(len(variables))-R_ess*np.transpose(np.matrix([active_power_ess_full["pred_"+str(s+1)]]))  
                                        for s in range(pred)}
                        }

        var["SOC_MAX"] = {"pred_"+str(s+1): np.array([90]*n_ess) for s in range(pred)}
        var["SOC_MIN"] = {"pred_"+str(s+1): np.array([10]*n_ess) for s in range(pred)}


        if VMAX:
            VMAX = VMAX#np.clip(VMAX, [0.95] * int(n), [1.05] * int(n)).tolist()
            VMIN = [0.95] * int(n)       # create array of VMIN     
        else:
            VMAX = [1.05] * int(n)       # create array of VMAX
            VMIN = [0.95] * int(n)       # create array of VMIN 

        SoC_dict = {"k":{"pred_"+str(s+1): SoC_full["pred_"+str(s+1)] for s in range(pred)},"k-1":{"pred_"+str(s+1): SoC_full["pred_"+str(s+1)] for s in range(pred)}}
        eta = 0.6


        b_ub = {}
        b_lb = {}
        b_u = {}
        b_l = {}
        b_u_2 = {}
        b_l_2 = {}
        b_rate_ub = {}
        b_rate_lb = {}
        A = {}
        A_2 = {}
        A_rate = {}
        A_ref = {}
        W = {}

        AA_ = {}
        BB_U = {}
        BB_L = {}

        W_tot = {}
        q_tot = {}
        A_tot = {}
        B_tot_U = {}
        B_tot_L = {}

        sol = {}
         

        for s in range(pred):
            p_ref["pred_"+str(s+1)] = np.transpose(np.matrix(var["ref"]["active_power"]["pred_"+str(s+1)]))
            q_ref["pred_"+str(s+1)] = np.transpose(np.matrix(var["ref"]["reactive_power"]["pred_"+str(s+1)]))
            p_ess_ref["pred_"+str(s+1)] = np.transpose(np.matrix(var["ref"]["active_power_ess"]["pred_"+str(s+1)]))

        logging.info("q_ref " + str(q_ref))
        
        X_n = X#np.matrix(np.diag(np.diag(X))) 
        R_n = R#np.matrix(np.diag(np.diag(R))) 

        A['active_power'] = R_n
        A['reactive_power'] = X_n
        A["active_power_ess"] = R_ess

        b_u["reactive_power"] = {"pred_"+str(s+1): (np.transpose(np.matrix([np.array(VMAX)]))/(len(variables))-var["VNOM"]["reactive_power"]["pred_"+str(s+1)]) for s in range(pred)}
        b_u["active_power"] = {"pred_"+str(s+1): (np.transpose(np.matrix([np.array(VMAX)]))/(len(variables))-var["VNOM"]["active_power"]["pred_"+str(s+1)]) for s in range(pred)}
        b_u["active_power_ess"] = {"pred_"+str(s+1): (np.transpose(np.matrix([np.array(VMAX)]))/(len(variables))-var["VNOM"]["active_power_ess"]["pred_"+str(s+1)]) for s in range(pred)}
        
        b_l["reactive_power"] = {"pred_"+str(s+1): (np.transpose(np.matrix([np.array(VMIN)]))/(len(variables))-var["VNOM"]["reactive_power"]["pred_"+str(s+1)]) for s in range(pred)}
        b_l["active_power"] = {"pred_"+str(s+1): (np.transpose(np.matrix([np.array(VMIN)]))/(len(variables))-var["VNOM"]["active_power"]["pred_"+str(s+1)]) for s in range(pred)}
        b_l["active_power_ess"] = {"pred_"+str(s+1): (np.transpose(np.matrix([np.array(VMIN)]))/(len(variables))-var["VNOM"]["active_power_ess"]["pred_"+str(s+1)]) for s in range(pred)}

        b_ub["active_power"] = {"pred_"+str(s+1): np.transpose(np.matrix([var["PMAX"]["pred_"+str(s+1)]])) for s in range(pred)}
        b_ub["active_power_ess"] = {"pred_"+str(s+1): np.transpose(np.matrix([var["PMAX_ESS"]["pred_"+str(s+1)]])) for s in range(pred)}
        b_ub["reactive_power"] = {"pred_"+str(s+1): np.transpose(np.matrix([var["QMAX"]["pred_"+str(s+1)]])) for s in range(pred)}
        b_ub["voltage"] = np.transpose(np.matrix([VMAX]))

        b_lb["active_power"] = {"pred_"+str(s+1): np.transpose(np.matrix([var["PMIN"]["pred_"+str(s+1)]])) for s in range(pred)}
        b_lb["active_power_ess"] = {"pred_"+str(s+1): np.transpose(np.matrix([var["PMIN_ESS"]["pred_"+str(s+1)]])) for s in range(pred)}
        b_lb["reactive_power"] = {"pred_"+str(s+1): np.transpose(np.matrix([var["QMIN"]["pred_"+str(s+1)]])) for s in range(pred)}
        b_lb["voltage"] = np.transpose(np.matrix([VMIN])) 

        W["reactive_power"] = np.diag(1*np.eye(n))
        W["active_power"] = np.diag(1*np.eye(n))
        W_V = np.diag(2*np.eye(n))
        W["active_power_ess"] = np.power(eta,2)*np.diag(0.01*np.eye(n))

        for variable in variables:
            W[variable] = W[variable]*modify_obj_function[variable]

        diff = np.max(A["active_power"]/A["reactive_power"])
        
        ########### Matrixes  ##################################   
            
        AA_["active_power"] = block_diag(*([np.concatenate((A["active_power"],np.eye(n))) for s in range(pred)]))
        BB_U["active_power"] = np.concatenate([np.concatenate((b_u["active_power"]["pred_"+str(s+1)]+A["active_power"]*p_ref["pred_"+str(s+1)],b_ub["active_power"]["pred_"+str(s+1)]+p_ref["pred_"+str(s+1)])) for s in range(pred)])
        BB_L["active_power"] = np.concatenate([np.concatenate((b_l["active_power"]["pred_"+str(s+1)]+A["active_power"]*p_ref["pred_"+str(s+1)],b_lb["active_power"]["pred_"+str(s+1)]+p_ref["pred_"+str(s+1)])) for s in range(pred)])

        AA_["reactive_power"] = block_diag(*([np.concatenate((A["reactive_power"],np.eye(n))) for s in range(pred)]))
        BB_U["reactive_power"] = np.concatenate([np.concatenate((b_u["reactive_power"]["pred_"+str(s+1)]+diff*A["reactive_power"]*q_ref["pred_"+str(s+1)],b_ub["reactive_power"]["pred_"+str(s+1)]+q_ref["pred_"+str(s+1)])) for s in range(pred)])
        BB_L["reactive_power"] = np.concatenate([np.concatenate((b_l["reactive_power"]["pred_"+str(s+1)]+diff*A["reactive_power"]*q_ref["pred_"+str(s+1)],b_lb["reactive_power"]["pred_"+str(s+1)]+q_ref["pred_"+str(s+1)])) for s in range(pred)])

        AA_["active_power_ess"] = block_diag(*([np.concatenate((A["active_power_ess"], np.eye(n))) for s in range(pred)]))
        BB_U["active_power_ess"] = np.concatenate([np.concatenate((b_u["active_power_ess"]["pred_"+str(s+1)]+A["active_power_ess"]*p_ess_ref["pred_"+str(s+1)],
                                                                    b_ub["active_power_ess"]["pred_"+str(s+1)]+p_ess_ref["pred_"+str(s+1)])) for s in range(pred)])
        BB_L["active_power_ess"] = np.concatenate([np.concatenate((b_l["active_power_ess"]["pred_"+str(s+1)]+A["active_power_ess"]*p_ess_ref["pred_"+str(s+1)],
                                                                    b_lb["active_power_ess"]["pred_"+str(s+1)]+p_ess_ref["pred_"+str(s+1)])) for s in range(pred)])

        var["infeasibility_output"] = {variable: None for variable in ["active_power","reactive_power","active_power_ess"]}
        ########## SEPARATED ######################################################        
        ########## Problem definition Reactive Power ##############################
        
        W_tot["reactive_power"] = block_diag(*([np.diag(W["reactive_power"]) for s in range(pred)]))
        q_tot["reactive_power"] = np.concatenate([np.array([0]*n) for s in range(pred)])
        A_tot["reactive_power"] = AA_["reactive_power"]
        B_tot_U["reactive_power"] = BB_U["reactive_power"]
        B_tot_L["reactive_power"] = BB_L["reactive_power"]

        W_tot["active_power"] = block_diag(*([np.diag(W["active_power"]) for s in range(pred)]))
        q_tot["active_power"] = np.concatenate([np.array([0]*n) for s in range(pred)])
        A_tot["active_power"] = AA_["active_power"]
        B_tot_U["active_power"] = BB_U["active_power"]
        B_tot_L["active_power"] = BB_L["active_power"]

        W_tot["active_power_ess"] = block_diag(*([np.diag(W["active_power_ess"]) for s in range(pred)]))
        q_tot["active_power_ess"] = np.concatenate([activate_SoC*2*np.array(np.transpose(-np.matrix(SoC_dict["k-1"]["pred_"+str(s+1)]-SoC_ref_full["pred_"+str(s+1)])*np.diag(W["active_power_ess"]))).flatten()+np.array([0]*n) for s in range(pred)])
        A_tot["active_power_ess"] = AA_["active_power_ess"]
        B_tot_U["active_power_ess"] = BB_U["active_power_ess"]
        B_tot_L["active_power_ess"] = BB_L["active_power_ess"]

        
        W_tot_fin = block_diag(*([W_tot[z] for z in variables]))
        q_tot_fin = np.concatenate(([q_tot[z] for z in variables]))
        A_tot_fin = block_diag(*([A_tot[z] for z in variables]))
        B_tot_U_fin = np.concatenate(([B_tot_U[z] for z in variables]))
        B_tot_L_fin = np.concatenate(([B_tot_L[z] for z in variables]))
           

        P = sparse.csc_matrix(W_tot_fin)
        q = np.array(q_tot_fin)
        A = sparse.csc_matrix(A_tot_fin)
        u = B_tot_U_fin
        l = B_tot_L_fin

        prob = osqp.OSQP()
        prob.setup(P=P, q=q, A=A, l=l, u=u, verbose = False)
        res = prob.solve()

        for k in range(len(variables)):
            sol[variables[k]] = res.x[k*n*pred:(k+1)*n*pred]

        if "active_power" not in variables:
            sol["active_power"] = [0.0]*n*pred
        if "reactive_power" not in variables:
            sol["reactive_power"] = [0.0]*n*pred
        if "active_power_ess" not in variables:
            sol["active_power_ess"] = [0.0]*n*pred

        if res.info.status == 'primal infeasible':
            logging.warning('primal infeasible')
            if any(np.array(v_tot)[i]>np.array(VMAX)[i] for i in range(n)):
                if iteration!=0:
                    var["infeasibility_output"]["reactive_power"] = np.tile(reactive_power_full["pred_1"],pred)
                    var["infeasibility_output"]["active_power"] = np.tile(active_power_full["pred_1"],pred)
                    var["infeasibility_output"]["active_power_ess"] = np.tile(active_power_ess_full["pred_1"],pred)
                else:
                    var["infeasibility_output"]["reactive_power"] = np.tile(var["QMIN"]["pred_1"],pred)
                    var["infeasibility_output"]["active_power"] = np.tile(var["PMIN"]["pred_1"],pred)
                    var["infeasibility_output"]["active_power_ess"] = np.tile(var["PMIN_ESS"]["pred_1"],pred)
            elif any(np.array(v_tot)[i]<np.array(VMIN)[i] for i in range(n)):
                if iteration!=0:
                    var["infeasibility_output"]["reactive_power"] = np.tile(reactive_power_full["pred_1"],pred)
                    var["infeasibility_output"]["active_power"] = np.tile(active_power_full["pred_1"],pred)
                    var["infeasibility_output"]["active_power_ess"] = np.tile(active_power_ess_full["pred_1"],pred)
                else:
                    var["infeasibility_output"]["reactive_power"] = np.tile(var["QMAX"]["pred_1"],pred)
                    var["infeasibility_output"]["active_power"] = np.tile(var["PMAX"]["pred_1"],pred)
                    var["infeasibility_output"]["active_power_ess"] = np.tile(var["PMAX_ESS"]["pred_1"],pred)
            else:
                var["infeasibility_output"]["reactive_power"] = np.tile(reactive_power_full["pred_1"],pred)
                var["infeasibility_output"]["active_power"] = np.tile(active_power_full["pred_1"],pred)
                var["infeasibility_output"]["active_power_ess"] = np.tile(active_power_ess_full["pred_1"],pred)
        else:
            var["infeasibility_output"]["reactive_power"] = sol["reactive_power"]
            var["infeasibility_output"]["active_power"] = sol["active_power"]
            var["infeasibility_output"]["active_power_ess"] = sol["active_power_ess"]

        if "active_power" not in variables:
            var["infeasibility_output"]["active_power"] = [0.0]*n*pred
        if "reactive_power" not in variables:
            var["infeasibility_output"]["reactive_power"] = [0.0]*n*pred
        if "active_power_ess" not in variables:
            var["infeasibility_output"]["active_power_ess"] = [0.0]*n*pred        

        var["q_sol"] = {"pred_"+str(s+1): var["infeasibility_output"]["reactive_power"][s*n:(n+s*n)]-np.array(q_ref["pred_"+str(s+1)]).flatten() for s in range(pred)}
        var["p_sol"] = {"pred_"+str(s+1): var["infeasibility_output"]["active_power"][s*n:(n+s*n)]-np.array(p_ref["pred_"+str(s+1)]).flatten() for s in range(pred)}
        var["p_ess_sol"] = {"pred_"+str(s+1): var["infeasibility_output"]["active_power_ess"][s*n:(n+s*n)]-np.array(p_ess_ref["pred_"+str(s+1)]).flatten() for s in range(pred)}

       
        if var["q_sol"]:
            reactive_power_sol = var["q_sol"]
        else:
            for s in range(pred):
                reactive_power_sol = {"pred_"+str(s+1): np.array([0.0]*n) for s in range(pred)}    

        if var["p_sol"]:
            active_power_sol = var["p_sol"]
        else:
            for s in range(pred):
                active_power_sol = {"pred_"+str(s+1): np.array([0.0]*n) for s in range(pred)}    
        
        if var["p_ess_sol"]:
            active_power_ess_sol = var["p_ess_sol"]
        else:
            for s in range(pred):
                active_power_ess_sol = {"pred_"+str(s+1): np.array([0.0]*n) for s in range(pred)}

        if resize == "yes":
            for s in range(pred):
                [reactive_power_sol["pred_"+str(s+1)], active_power_sol["pred_"+str(s+1)],active_power_ess_sol["pred_"+str(s+1)], SoC_dict["k"]["pred_"+str(s+1)], SoC_dict["k-1"]["pred_"+str(s+1)]] = additional.resize_out(active_nodes,reactive_power_sol["pred_"+str(s+1)],active_power_sol["pred_"+str(s+1)],active_power_ess_sol["pred_"+str(s+1)], SoC_dict["k"]["pred_"+str(s+1)], SoC_dict["k-1"]["pred_"+str(s+1)])
        else:
            pass

        for s in range(pred):
            SoC_dict["k"]["pred_"+str(s+1)] = SoC_dict["k-1"]["pred_"+str(s+1)] - eta*active_power_ess_sol['pred_'+str(s+1)]

        return  active_power_sol, reactive_power_sol, active_power_ess_sol, SoC_dict["k"], v_tot_dict