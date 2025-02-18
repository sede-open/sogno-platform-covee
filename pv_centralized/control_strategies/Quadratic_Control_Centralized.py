import control_strategies.quadratic_control_centralized as quadratic_control
import numpy as np
from cvxopt import matrix, solvers
import picos as pic

class Quadratic_Control_Centralized():

    def __init__(self, grid_data, num_pv, num_ESS):

        self.grid_data = grid_data	
        self.num_pv = num_pv
        self.num_bus = self.grid_data["nb"]
        self.num_ESS = num_ESS
        self.QMIN = []
        self.QMAX = []
        self.PMIN = []
        self.PMAX = []
        self.PMIN_ESS = []
        self.PMAX_ESS = []

        # Problem parameters
        # =============================================================
        self.V_MIN = 0.95  # undervoltage limit
        self.V_MAX = 1.050  # overvoltage limit
        # Initialize LIM
        # =============================================================
        for i in range(int(len(self.num_pv))):
            self.QMIN.append(-0.8)
            self.QMAX.append(0.8)
            self.PMIN.append(-3.0)
            self.PMAX.append(+3.0)
            self.PMIN_ESS.append(-3.0)
            self.PMAX_ESS.append(+3.0)

    def initialize_control(self): 

        self.num_pv = list(np.array(self.num_pv)-1)
        calculate_matrix_PV = quadratic_control.matrix_calc(self.grid_data, self.num_pv) 
        [self.R,self.X] = calculate_matrix_PV.calculate()
        return self.R,self.X
  
    def control_(self, PV_list, q_PV, active_power_PV, v_gen, active_power_battery, v_ess):
        
        n = len(self.num_pv)
        # DEFINE LIM (DYNAMIC)
        # =============================================================
        for i in range(int(len(self.num_pv))):
            self.QMIN[i] = -0.312*(PV_list[i]+1e-2)   # 40% of the available power
            self.QMAX[i] = 0.312*(PV_list[i]+1e-2)    # 40% of the available power
            self.PMIN[i] = -PV_list[i]
            self.PMAX[i] = 0.0
            self.PMIN_ESS[i] = -0.8
            self.PMAX_ESS[i] = 0.8           
        
        self.VMAX = [self.V_MAX] * int(len(self.num_pv))       # create array of VMAX
        self.VMIN = [self.V_MIN] * int(len(self.num_pv))       # create array of VMIN    
        self.VNOM = np.transpose(np.matrix(v_gen))-R*np.transpose(np.matrix([active_power_PV])+np.matrix([active_power_battery]))
                    -X*np.transpose(np.matrix([q_PV]))

        b_ub = {}
        b_lb = {}
        b = {}

        W_Q = np.diag(1*np.eye(n))
        W_P = np.diag(1*np.eye(n))
        W_ESS = np.diag(1*np.eye(n))
        # W_V = np.diag(1*np.eye(n))

        b["active_power_PV"] = np.transpose(np.matrix([np.array(self.VMAX)]))-self.VNOM
        b["reactive_power_PV"] = np.transpose(np.matrix([np.array(self.VMAX)]))-self.VNOM
        b["active_power_ESS"] = np.transpose(np.matrix([np.array(self.VMAX)]))-self.VNOM

        ############# Box Contraints #################################
        # Upper boundaries
        b_ub["active_power_PV"] = np.transpose(np.matrix([self.PMAX]))
        b_ub["reactive_power_PV"] = np.transpose(np.matrix([self.QMAX]))    
        b_ub["active_power_ESS"] = np.transpose(np.matrix([self.PMAX_ESS]))       
        # Lower boundaries
        b_lb["active_power_PV"] = np.transpose(np.matrix([self.PMAX]))
        b_lb["reactive_power_PV"] = np.transpose(np.matrix([self.QMAX]))    
        b_lb["active_power_ESS"] = np.transpose(np.matrix([self.PMAX_ESS])) 

        ########### Matrixes  ################################## 
        # AA_V = np.concatenate((np.eye(n), -np.eye(n)))
        # BB_V = np.concatenate((b_ub["voltage"], -b_lb["voltage"]))        

        
        AA_P = np.concatenate((self.R,np.eye(n), -np.eye(n)))
        BB_P = np.concatenate((b["active_power"],b_ub["active_power"], -b_lb["active_power"]))

        AA_Q = 
        BB_Q = 
        ##########################################################            

        return self.reactive_power, self.active_power_PV, self.active_power_battery


        




