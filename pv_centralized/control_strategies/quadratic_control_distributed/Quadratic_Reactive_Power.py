import numpy as np
from pypower.ppoption import ppoption
from .algorithms.algorithms import algorithms


class Quadratic_Reactive_Power:

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

        self.q = [0.0] * int(len(self.c))

        self.QMIN = []
        self.QMAX = []

        # Control Parameters
        # ==============================================================
        self.K = 10   # iterations of the voltage control

        self.alpha = [0.3]* int(len(self.c))  # this value is not the one used. It is calculated in Quadratic Control
        self.lamda_max = [0.0]* int(len(self.c))
        self.lamda_min = [0.0]* int(len(self.c))
        self.mu_min = [1e-6] * int(len(self.c))
        self.mu_max = [1e-6] * int(len(self.c))

        # DEFINE LIM
        # =============================================================
        for i in range(int(len(self.c))):
            self.QMIN.append(-0.8)
            self.QMAX.append(0.8)

    def initialize_control(self):
       
        self.VMAX = [self.V_MAX] * int(len(self.c))
        
        param = algorithms(baseMVA=self.baseMVA, bus=self.bus, branch=self.branch, c=self.c, pcc = self.pcc, nbr =self.nbr)
        self.G = param.g_parameter()[0]
        self.X = param.g_parameter()[1]
        self.gamma = 1/(2*np.linalg.norm(self.G))

        return self.q, self.mu_min


    def Voltage_Control(self, pv_production, reactive_power, v_gen, alpha): 
        self.pvproduction = pv_production
        self.q = reactive_power
        self.v_gen = v_gen
        self.alpha = alpha
        # print("pv production", pv_production)

        # DEFINE LIM (DYNAMIC)
        # =============================================================
        for i in range(int(len(self.c))):
            self.QMIN[i] = -0.312*(self.pvproduction[i]+1e-2)   # 40% of the available power
            self.QMAX[i] = 0.312*(self.pvproduction[i]+1e-2)    # 40% of the available power
            # self.QMIN = [-1.0,-0.2]                         # BOLOGNANI TEST
            # self.QMAX = [1.0,0.2]                           # BOLOGNANI TEST
        self.VMAX = [self.V_MAX] * int(len(self.c))       # create array of VMAX
        self.VMIN = [self.V_MIN] * int(len(self.c))       # create array of VMIN     

        ############# REACTIVE POWER CONTROL ###############################  
        lan_multi = algorithms(lamda_max=self.lamda_max,lamda_mín=self.lamda_min,alpha=self.alpha,v=self.v_gen, VMAX=self.VMAX,
                            VMIN=self.VMIN, ng=int(len(self.c)),delta_t = 0.98)
        self.lamda_max = lan_multi.network_compensation()[0]
        self.lamda_min = lan_multi.network_compensation()[1]
        q_calc = algorithms(lamda_max=self.lamda_max,lamda_mín=self.lamda_min,K=self.K,mu_min=self.mu_min, mu_max=self.mu_max,gamma=self.gamma,
                            G=self.G,QMIN=self.QMIN,QMAX = self.QMAX,ng=int(len(self.c)),qhat_pre=self.q,delta_t = 0.98, X = self.X)
        self.q = q_calc.inner_loop()[0]
        self.mu_min = q_calc.inner_loop()[1]
        self.mu_max = q_calc.inner_loop()[2]

        return self.q, self.mu_min