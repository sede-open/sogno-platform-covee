import numpy as np
from pypower.ppoption import ppoption
from .algorithms.algorithms_controllable_loads import algorithms_controllable_loads


class Quadratic_Active_Power_PV:

    def __init__(self, grid_data, num_pv):
        # Input Data
        # =============================================================
        '''
        data 0 : bus
        data 1 : baseMVA
        data 2 : branch
        data 3 : pcc
        data 4 : nb
        data 5 : ng
        data 6 : nbr
        data 7 : c
        '''
        self.bus = grid_data["bus"]
        self.baseMVA = grid_data["baseMVA"]
        self.branch = grid_data["branch"]
        self.pcc = grid_data["pcc"]
        self.nb = grid_data["nb"]
        self.ng = grid_data["ng"]
        self.nbr = grid_data["nbr"]
        self.c = num_pv

        # Problem parameters
        # =============================================================
        self.V_MIN = 0.9  # undervoltage limit
        self.V_MAX = 1.1 # overvoltage limit

        self.p_PV = [0.0] *len(self.c)

        self.PMIN = []
        self.PMAX = []


    def initialize_control(self):

        # DEFINE LIM
        # =============================================================
        for i in range(len(self.c)):
            self.PMIN.append(-3.0)
            self.PMAX.append(+3.0)

        self.VMAX_PV = [self.V_MAX] * int(len(self.c))
        self.VMIN_PV = [self.V_MIN] * int(len(self.c))

        # Control Parameters
        # ==============================================================
        self.K = 10 # iterations of the voltage control

        self.alpha_p = [1]* int(len(self.c))
        self.lamda_p_max = [0.0]* int(len(self.c))
        self.lamda_p_min = [0.0]* int(len(self.c))
        self.xi_max = [1e-6] * int(len(self.c))
        self.xi_min = [1e-6] * int(len(self.c))

        param_p = algorithms_controllable_loads(baseMVA=self.baseMVA, bus=self.bus, branch=self.branch, c=self.c, pcc = self.pcc, nbr =self.nbr, n_battery=self.c)
        self.G_p = param_p.g_parameter()[0]
        self.X = param_p.g_parameter()[1]
        self.gamma_p = 1/(2*np.linalg.norm(self.G_p))

        return self.p_PV, self.alpha_p


    def Voltage_Control(self, pv_production, p_PV, v_gen, alpha):
        self.pvproduction = pv_production
        self.v_gen = v_gen
        self.p_PV = p_PV
        self.alpha_p = alpha

        # DEFINE LIM (DYNAMIC)
        # =============================================================
        for i in range(len(self.c)):
            self.PMIN[i] = -self.pvproduction[i]
            self.PMAX[i] = 0.0*self.pvproduction[i]

        self.VMAX_PV = [self.V_MAX] * int(len(self.c))
        self.VMIN_PV = [self.V_MIN] * int(len(self.c))        

        ############# CALCULATE PV ACTIVE POWER CONTROL ######################################## 
        lan_multi_p = algorithms_controllable_loads(lamda_max=self.lamda_p_max, lamda_min=self.lamda_p_min, alpha=self.alpha_p, v=self.v_gen,
                                                    VMAX=self.VMAX_PV, VMIN=self.VMIN_PV, ng=self.c,delta_t = 0.98)
        self.lamda_p_max = lan_multi_p.network_compensation()[0]
        self.lamda_p_min = lan_multi_p.network_compensation()[1]
        p_calc = algorithms_controllable_loads(lamda=self.lamda_p_max,lamda_min=self.lamda_p_min,K=self.K,xi_min=self.xi_min,xi_max=self.xi_max,gamma=self.gamma_p,
                                            G_p=self.G_p,PMAX=self.PMAX, PMIN=self.PMIN, ng=self.c, phat_pre=self.p_PV,delta_t = 0.98, X = self.X)
        self.p_PV = p_calc.inner_loop()[0]
        self.xi_max = p_calc.inner_loop()[1]
        self.xi_min = p_calc.inner_loop()[2]

        return self.p_PV