import numpy as np
from .algorithms.algorithms import algorithms
from .algorithms.algorithms_controllable_loads import algorithms_controllable_loads
from scipy.linalg import block_diag

class iteration_calculation:

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
        self.c = num_pv#grid_data[7]


    def calculate_alpha(self):
        GAMMA = []
        
        # Control Parameters
        # ==============================================================
        self.alpha = [10.0]* int(len(self.c))
        self.lamda_max = [0.0]* int(len(self.c))
        self.lamda_min = [0.0]* int(len(self.c))
        self.mu_min = [0.0] * int(len(self.c))
        self.mu_max = [0.0] * int(len(self.c))

        param = algorithms(baseMVA=self.baseMVA, bus=self.bus, branch=self.branch, c=self.c, pcc = self.pcc, nbr =self.nbr)
        self.G = param.g_parameter()[0]        
        self.X = param.g_parameter()[1]
        self.gamma = 1/(2*np.linalg.norm(self.G))
    
        I = np.eye(int(len(self.c)))

        X = np.asmatrix(np.imag(self.X))
        PHI = np.asmatrix(np.concatenate((-X,X)))
        I_big = np.block([[I,-I],[-I,I]])
        G = np.matrix(self.G)
        lim = 1/np.max(np.abs(np.linalg.eigvals(PHI*G*np.transpose(PHI))))#2/(np.linalg.norm(PHI*G*np.transpose(PHI)))

        return lim

    # def calculate_alphaP(self):
    #     GAMMA = []
        
    #     # Control Parameters
    #     # ==============================================================
    #     self.alpha_p = [0.3]* int(len(self.n_battery))
    #     self.lamda_p_max = [0.0]* int(len(self.n_battery))
    #     self.lamda_p_min = [0.0]* int(len(self.n_battery))
    #     self.xi_max = [0.0] * int(len(self.n_battery))
    #     self.xi_min = [0.0] * int(len(self.n_battery))

    #     param_p = algorithms_controllable_loads(baseMVA=self.baseMVA, bus=self.bus, branch=self.branch, c=self.c, pcc = self.pcc, nbr =self.nbr, n_battery=self.n_battery)
    #     self.G_p = param_p.g_parameter()[0]
    #     self.X = param_p.g_parameter()[1]
    #     self.gamma_p = 1/(2*np.linalg.norm(self.G_p))
    
    #     I = np.eye(int(len(self.n_battery)))

    #     X = np.asmatrix(np.imag(self.X))
    #     PHI = np.asmatrix(np.concatenate((-X,X)))
    #     I_big = np.block([[I,-I],[-I,I]])
    #     G_p = np.matrix(self.G_p)
    #     lim_p = 1/np.max(np.abs(np.linalg.eigvals(PHI*G_p*np.transpose(PHI))))#2/(np.linalg.norm(PHI*G*np.transpose(PHI)))

    #     return lim_p