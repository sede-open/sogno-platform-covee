import numpy as np
from .algorithms.algorithms_controllable_loads import algorithms_controllable_loads
from pulp import *
from scipy.optimize import linprog


class Linear_Active_Power_PV():

    def __init__(self, grid_data):
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
        self.bus = grid_data[0]
        self.baseMVA = grid_data[1]
        self.branch = grid_data[2]
        self.pcc = grid_data[3]
        self.nb = grid_data[4]
        self.ng = grid_data[5]
        self.nbr = grid_data[6]
        self.c = grid_data[7]

        # Problem parameters
        # =============================================================
        self.V_MIN = 0.9  # undervoltage limit
        self.V_MAX = 1.5 # overvoltage limit

        self.V_MIN2 = 0.95  # undervoltage limit 2
        self.V_MAX2 = 1.05  # overvoltage limit 2

        self.PMIN = []
        self.PMAX = []

        self.p_PV_array = [0.0] *len(self.c)
        self.v_PV = [0.0] *len(self.c)
        self.p_PV = [0.0] *len(self.c)


    def initialize_control(self):

        # DEFINE LIM
        # =============================================================
        for i in range(len(self.c)):
            self.PMIN.append(-3.0)
            self.PMAX.append(+3.0)

        self.VMAX_PV = [self.V_MAX2] * int(len(self.c))
        self.VMIN_PV = [self.V_MIN2] * int(len(self.c))

        # Control Parameters
        # ==============================================================

        param_p = algorithms_controllable_loads(baseMVA=self.baseMVA, bus=self.bus, branch=self.branch, c=self.c, pcc = self.pcc, nbr =self.nbr, n_battery=self.c)
        self.G_p = param_p.g_parameter()[0]
        self.X = param_p.g_parameter()[1]
        self.gamma_p = 1/(2*np.linalg.norm(self.G_p))

        return self.p_PV
    
    def Voltage_Control(self, k, pv_production, p_PV, v_gen):
        self.pvproduction = pv_production
        p = p_PV.tolist()
        self.v_gen = v_gen

        # DEFINE LIM (DYNAMIC)
        # =============================================================
        for i in range(len(self.c)):
            self.PMIN[i] = -0.312*self.pvproduction[k][i]
            self.PMAX[i] = 0.0*self.pvproduction[k][i]

        self.VMAX = [self.V_MAX2] * int(len(self.c))
        self.VMIN = [self.V_MIN2] * int(len(self.c))   

        self.set_I = range(1,int(len(self.c))+1)
        self.set_J = range(1,int(len(self.c))+1)
        C = [1]*len(self.c)

        self.b = {}
        for i in range(len(self.set_I)):
            self.b[self.set_I[i]] = self.VMAX[i]-self.v_gen[i]

        # =========================================================================================
        # SCIPY OPTIMIZER
        # =========================================================================================

        A = (-np.matrix(np.real(self.X))).tolist()
        b_2 = list(self.b.values())
        
        bounds = ((0.0-p[0],-self.PMIN[0]-p[0]),)         
        for i in range(1,len(self.c)):
            bounds += ((0.0-p[i],-self.PMIN[i]-p[i]),)

        DQ = linprog(C, A_ub=A, b_ub=b_2, bounds=(bounds))
            
        p = 0.5*np.array(DQ.x) + np.array(p)


        return (-p).tolist()


