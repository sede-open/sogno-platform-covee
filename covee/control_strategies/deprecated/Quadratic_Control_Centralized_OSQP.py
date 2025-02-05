import numpy as np
from cvxopt import matrix, solvers
import matplotlib.pyplot as plt
from scipy.linalg import block_diag
import os
import osqp
from scipy import sparse
import coloredlogs, logging, threading

import control_strategies.quadratic_control as quadratic_control


class Quadratic_Control():

    def __init__(self, grid_data, num_pv,num_ESS):
        self.grid_data = grid_data	
        self.num_pv = num_pv
        self.num_bus = self.grid_data["nb"]     


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

        self.num_pv = np.array(self.num_pv).tolist()
        self.bus_values = np.array(list(range(1,self.num_bus))).tolist()
        calculate_matrix_full = quadratic_control.matrix_calc(self.grid_data, self.bus_values) 
        [R,X] = calculate_matrix_full.calculate()
        self.additional = quadratic_control.additional(self.bus_values)

        self.P_activate = [1e6]*len(self.bus_values)
      
        return R,X

    def control_(self, pvproduction, active_power, reactive_power, R, X, active_nodes, v_tot, active_power_battery, v_ess):

        full_nodes = self.bus_values
        n = len(self.bus_values)        

        [reactive_power_full, active_power_full, pv_input_full, full_active] = self.additional.resize_in(full_nodes,active_nodes,active_power,
                                                                                                                    reactive_power,pvproduction,n)

        k = 0
        var= {}
        var["ref"] =  {"active_power": np.array([0.0]*n), "voltage": np.array([-0.0]*n)}
        var["QMIN"] = np.array([-0.312*pv_input_full[i] for i in range(int(n))])
        var["QMAX"] = np.array([0.312*pv_input_full[i] for i in range(int(n))])
        var["PMIN"] = np.array([-(pv_input_full[i]+1e-6) for i in range(int(n))])
        var["PMAX"] = np.array([0.0+1e-6 for i in range(int(n))])
        var["VNOM"] = {"active_power": np.transpose(np.matrix(v_tot))-R*np.transpose(np.matrix([active_power_full])), 
                        "reactive_power": np.transpose(np.matrix(v_tot))-X*np.transpose(np.matrix([reactive_power_full]))}
        infeasibility_output = {"active_power": None, "reactive_power": None}

      
        self.VMAX = [self.V_MAX] * int(n)       # create array of VMAX
        self.VMIN = [self.V_MIN] * int(n)       # create array of VMIN    

        b_ub = {}
        b_lb = {}
        b_u = {}
        b_l = {}
        b_rate_ub = {}
        b_rate_lb = {}
        A = {}
        A_rate = {}

        A['active_power'] = R
        A['reactive_power'] = X

        b_u["reactive_power"] = np.transpose(np.matrix([np.array(self.VMAX)]))-var["VNOM"]["reactive_power"]
        b_u["active_power"] = np.transpose(np.matrix([np.array(self.VMAX)*np.array(self.P_activate)]))-var["VNOM"]["active_power"]
        
        b_l["reactive_power"] = np.transpose(np.matrix([np.array(self.VMIN)]))-var["VNOM"]["active_power"]
        b_l["active_power"] = np.transpose(np.matrix([np.array(self.VMIN)]))-var["VNOM"]["active_power"]
        
        b_ub["active_power"] = np.transpose(np.matrix([var["PMAX"]]))
        b_ub["reactive_power"] = np.transpose(np.matrix([var["QMAX"]]))
        b_ub["voltage"] = np.transpose(np.matrix([self.VMAX]))

        b_lb["active_power"] = np.transpose(np.matrix([var["PMIN"]]))
        b_lb["reactive_power"] = np.transpose(np.matrix([var["QMIN"]]))
        b_lb["voltage"] = np.transpose(np.matrix([self.VMIN])) 


        W_Q = np.diag(1*np.eye(n)*full_active)
        W_P = np.diag(1*np.eye(n)*full_active)
        W_V = np.diag(1*np.eye(n)*full_active)
    

        p_ref = var["ref"]["active_power"]
        v_ref = var["ref"]["voltage"]

        ########### Matrixes  ################################## 
        AA_V = np.concatenate((np.eye(n), -np.eye(n)))
        BB_V = np.concatenate((b_ub["voltage"], -b_lb["voltage"]))        

        
        AA_P = np.concatenate((A["active_power"],np.eye(n)))
        BB_P_U = np.concatenate((b_u["active_power"],b_ub["active_power"]))
        BB_P_L = np.concatenate((b_l["active_power"],b_lb["active_power"]))

        AA_Q = np.concatenate((A["reactive_power"],np.eye(n)))
        BB_Q_U = np.concatenate((b_u["reactive_power"],b_ub["reactive_power"]))
        BB_Q_L = np.concatenate((b_l["reactive_power"],b_lb["reactive_power"]))
        ##########################################################
   
        ########## Problem definition ############################## 
        P_P = sparse.csc_matrix(2*np.diag(W_P))
        q_P = np.array([0]*n)
        A_P = sparse.csc_matrix(AA_P)
        u_P = BB_P_U
        l_P = BB_P_L

        P_Q = sparse.csc_matrix(2*np.diag(W_Q))
        q_Q = np.array([0]*n)
        A_Q = sparse.csc_matrix(AA_Q)
        u_Q = BB_Q_U
        l_Q = BB_Q_L
        
        prob = osqp.OSQP()
        prob.setup(P=P_Q, q=q_Q, A=A_Q, l=l_Q, u=u_Q, verbose = False)
        res = prob.solve()
        q_sol_centr = res.x

        if res.info.status == 'primal infeasible':
            logging.warning('primal infeasible')
        if any(np.array(v_tot)[i]-np.array(self.VMAX)[i]>0.01 for i in range(n)) and res.info.status == 'primal infeasible':
            infeasibility_output["reactive_power"] = var["QMIN"] 
        elif any(np.array(v_tot)[i]-np.array(self.VMIN)[i]<0.01 for i in range(n)) and res.info.status == 'primal infeasible':
            infeasibility_output["reactive_power"] = var["QMAX"]
        else:
            infeasibility_output["reactive_power"] = reactive_power_full

        prob.update(Px=P_P.data, q=q_P, Ax=A_P.data, l=l_P, u=u_P)
        res = prob.solve()
        p_sol_centr = res.x

        [reactive_power_sol, active_power_sol] = self.additional.resize_out(active_nodes,q_sol_centr,p_sol_centr,reactive_power_full,active_power_full, infeasibility_output["reactive_power"])

        self.P_activate = self.additional.prioritize(reactive_power_sol,var["QMIN"],self.P_activate,n,case='prioritize')

        return  active_power_sol.tolist(), reactive_power_sol.tolist(), active_power_battery