from __future__ import division
import numpy as np
from .algorithms.algorithms import algorithms
from pulp import *
from scipy.optimize import linprog
from pyomo.environ import SolverFactory
from pyomo.core import *


class Linear_Reactive_Power():

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
        self.V_MAX = 1.05 # overvoltage limit

        self.q = [0.0] * int(len(self.c))

        self.QMIN = []
        self.QMAX = []
        self.T = []
        self.VAR = []
        self.CONSTRAINTS = []

    def initialize_control(self):

        # DEFINE LIM
        # =============================================================
        for i in range(int(len(self.c))):
            self.QMIN.append(-0.8)
            self.QMAX.append(0.8)
        
        self.VMAX = [self.V_MAX] * int(len(self.c))
        
        # Control Parameters
        # ==============================================================
        self.K = 10   # iterations of the voltage control
        self.C = [1.0]*int(len(self.c))

        param = algorithms(baseMVA=self.baseMVA, bus=self.bus, branch=self.branch, c=self.c, pcc = self.pcc, nbr =self.nbr)
        self.G = param.g_parameter()[0]
        self.X = param.g_parameter()[1]  

        # LISTS
        for i in range(len(self.c)):
            self.T.append('T'+str(i+1))
            self.VAR.append(i+1)
            self.CONSTRAINTS.append('CON '+str(i+1))


        return self.q, self.X
    
    def Voltage_Control(self, k, pv_production, reactive_power, v_gen):
        self.pvproduction = pv_production
        q = reactive_power.tolist()
        self.v_gen = v_gen

        # DEFINE LIM (DYNAMIC)
        # =============================================================
        for i in range(int(len(self.c))):
            self.QMIN[i] = -0.312*(self.pvproduction[k][i]+1e-2)   # 40% of the available power
            self.QMAX[i] = 0.312*(self.pvproduction[k][i]+1e-2)    # 40% of the available power
            # self.QMIN = [-1.0,-0.2]                         # BOLOGNANI TEST
            # self.QMAX = [1.0,0.2]                           # BOLOGNANI TEST
           
        self.VMAX = [self.V_MAX] * int(len(self.c))       # create array of VMAX
        self.VMIN = [self.V_MIN] * int(len(self.c))       # create array of VMIN 

        # =========================================================================================
        # PulP Optimizer
        # =========================================================================================

        C = (sum(np.matrix(np.imag(self.X))[:,:])).tolist()

        self.c_dict = {}
        for i in range(len(self.VAR)):
                self.c_dict[self.VAR[i]] = C[0][i]


        A = -np.matrix(np.imag(self.X))
        I = -np.matrix(np.eye(len(self.c)))
        b = {}
        u = {}
        l = {}
        q_dict = {}
        x_vars = {}
        constraints = {}
        for i in range(len(self.c)):
            b[self.CONSTRAINTS[i]] = 1.05-self.v_gen[i]
            u[self.CONSTRAINTS[i]] = self.QMIN[i] + q[i]
        
        con1 = {}
        for i in range(len(self.CONSTRAINTS)):
            con1[self.CONSTRAINTS[i]] = {j: A[i,j-1] for j in self.VAR}

        con2 = {}
        for i in range(len(self.CONSTRAINTS)):
            con2[self.CONSTRAINTS[i]] = {j: I[i,j-1] for j in self.VAR}

        prob = LpProblem("MIP_Model", LpMinimize)

        x_vars  = LpVariable.dicts("x",[j for j in self.VAR], 0)
        
        volta_var = {}
        for i in range(len(self.CONSTRAINTS)):
            volta_var[self.CONSTRAINTS[i]] = {j: A[i,j-1]*x_vars[j] for j in self.VAR}

        prob += lpSum(x_vars[i]  for i in self.VAR)

        for j in self.CONSTRAINTS:
            prob += lpSum(con1[j][i]*x_vars[i] for i in self.VAR) <= b[j]
            prob += lpSum(con2[j][i]*x_vars[i] for i in self.VAR) <= u[j]
        
        # solving
        prob.solve()   
        # Print status.
        print("Status:", LpStatus[prob.status], "\n")
        # Each of the variables is printed with it's resolved optimum value
        value = []
        for v in prob.variables():
            value.append(v.varValue)
        result= []
        for i in range(len(value)-1):
            result.append(value[i+1])
        print("pulp reult", result)

        # =========================================================================================
        # SCIPY OPTIMIZER
        # =========================================================================================
        A = (-np.matrix(np.imag(self.X))).tolist()
        C = sum(np.matrix(np.imag(self.X))[:,:]).tolist()
        C = [1,1,1,1,100,1]
        b_2 = list(b.values())
        
        bounds = ((0.0-q[0],-self.QMIN[0]-q[0]),)         
        for i in range(1,len(self.c)):
            bounds += ((0.0-q[i],-self.QMIN[i]-q[i]),)


        DQ = linprog(C, A_ub=A, b_ub=b_2, bounds=(bounds))

   
        q = 0.5*np.array(DQ.x) + np.array(q)

        return (-q).tolist()


