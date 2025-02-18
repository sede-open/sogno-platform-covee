import numpy as np
from pypower.idx_brch import F_BUS, T_BUS, TAP, BR_R, BR_X, BR_B, RATE_A, PF, QF, PT, QT
from pypower.idx_bus import BUS_I
from pypower.makeYbus import makeYbus
from pypower.idx_bus import BUS_TYPE
from scipy.sparse import csr_matrix

class matrix_calc():

    def __init__(self,grid_data, num_pv):
        self.grid_data = grid_data
        self.num_pv = num_pv

    def calculate(self):
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
        bus = self.grid_data["bus"]
        baseMVA = self.grid_data["baseMVA"]
        branch = self.grid_data["branch"]
        pcc = self.grid_data["pcc"]
        nb = self.grid_data["nb"]
        ng = self.grid_data["ng"]
        nbr = self.grid_data["nbr"]
        c = self.num_pv

        # New version
        # calculate incidence matrix
        # =============================================================
        Ybus = makeYbus(baseMVA, bus, branch)[0]
        Ybus = Ybus.todense()
        # print("Y shape", np.shape(Ybus))

        # compute X as in [doi: 10.1109/TAC.2013.2270317]
        YY = np.zeros(((nb+1),(nb+1)),dtype=complex)
        YY[:-1,:-1]= Ybus

        YY[0,(nb)] = 1     # implemeted as bolognani paper
        YY[(nb),0] = 1

        XX = np.linalg.inv(YY)
        XX = np.delete(XX, nb, axis=0)
        XX = np.delete(XX, nb, axis=1)

        Xgg = XX
        Xgg = XX

        bus_i = []
        for j in range(nb):
            bus_i.append(bus[j][BUS_I])

        diff = list(set(bus_i)-set(c))
        diff = [int(i) for i in diff]

        Xgg = np.delete(Xgg, diff, axis=0)
        Xgg = np.delete(Xgg, diff, axis=1)

        # print(Xgg)

        #G = np.linalg.inv((np.matrix(np.imag(Xgg))))
        # print("G",(G))

        return np.matrix(np.real(Xgg)), np.matrix(np.imag(Xgg))
