import numpy as np
from pypower.ppoption import ppoption
from .algorithms.algorithms_controllable_loads import algorithms_controllable_loads


class Quadratic_Active_Power_Batt:

    def __init__(self, grid_data, node_with_battery):
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

        self.c = node_with_battery

        self.n_battery = node_with_battery

        # Problem parameters
        # =============================================================
        self.V_MIN = 0.9  # undervoltage limit
        self.V_MAX = 1.5 # overvoltage limit

        self.V_MIN2 = 0.9  # undervoltage limit 2
        self.V_MAX2 = 1.1  # overvoltage limit 2

        self.PMIN = []
        self.PMAX = []

        self.p_batt_array = [0.0] * (int(self.nb) - 1)
        self.v_bat = [0.0] *len(self.n_battery)
        self.p_batt = [0.0] *len(self.n_battery)


    def initialize_control(self):

        # DEFINE LIM
        # =============================================================
        for i in range(len(self.n_battery)):
            self.PMIN.append(-3.0)
            self.PMAX.append(+3.0)

        self.VMAX_BATT = [self.V_MAX2] * int(len(self.n_battery))
        self.VMIN_BATT = [self.V_MIN2] * int(len(self.n_battery))

        # Control Parameters
        # ==============================================================
        self.K = 10   # iterations of the voltage control

        self.alpha_p = [0.3]* int(len(self.n_battery))
        self.lamda_p_max = [0.0]* int(len(self.n_battery))
        self.lamda_p_min = [0.0]* int(len(self.n_battery))
        self.xi_max = [1e-6] * int(len(self.n_battery))
        self.xi_min = [1e-6] * int(len(self.n_battery))

        param_p = algorithms_controllable_loads(baseMVA=self.baseMVA, bus=self.bus, branch=self.branch, c=self.c, pcc = self.pcc, nbr =self.nbr, n_battery=self.n_battery)
        self.G_p = param_p.g_parameter()[0]
        self.X = param_p.g_parameter()[1]
        self.gamma_p = 1/(2*np.linalg.norm(self.G_p))

        return self.p_batt, self.alpha_p, self.xi_min	


    def Voltage_Control(self, p_batt, v_bat, alpha_P):
        self.v_bat = v_bat
        self.p_batt = p_batt
        self.alpha_p = alpha_P

        # DEFINE LIM (DYNAMIC)
        # =============================================================
        for i in range(len(self.n_battery)):
            self.PMIN[i] = -(0.8)
            self.PMAX[i] = (0.8)


        self.VMAX_BATT = [self.V_MAX2] * int(len(self.n_battery))
        self.VMIN_BATT = [self.V_MIN2] * int(len(self.n_battery))        

        ############# CALCULATE SOC/BATTERY ACTIVE POWER CONTROL ########################################
        lan_multi_p = algorithms_controllable_loads(lamda_max=self.lamda_p_max, lamda_min=self.lamda_p_min, alpha=self.alpha_p, v=self.v_bat,
                                                    VMAX=self.VMAX_BATT, VMIN=self.VMIN_BATT, n_battery=self.n_battery,delta_t = 0.98)
        self.lamda_p_max = lan_multi_p.network_compensation()[0]
        self.lamda_p_min = lan_multi_p.network_compensation()[1]
        p_calc = algorithms_controllable_loads(lamda=self.lamda_p_max,lamda_min=self.lamda_p_min,K=self.K,xi_min=self.xi_min,xi_max=self.xi_max,gamma=self.gamma_p,
                                            G_p=self.G_p,PMAX=self.PMAX, PMIN=self.PMIN, n_battery=self.n_battery, phat_pre=self.p_batt,delta_t = 0.98, X = self.X)
        self.p_batt = p_calc.inner_loop()[0]
        self.xi_max = p_calc.inner_loop()[1]
        self.xi_min = p_calc.inner_loop()[2]

        return self.p_batt, self.xi_min
