import numpy as np
from pypower.idx_brch import F_BUS, T_BUS, TAP, BR_R, BR_X, BR_B, RATE_A, PF, QF, PT, QT
from pypower.idx_bus import BUS_I
from pypower.makeYbus import makeYbus
from pypower.idx_bus import BUS_TYPE
from scipy.sparse import csr_matrix
import time

class algorithms:

    def __init__(self, **kwargs):
        self.data = []
        for key in kwargs:
            self.data.append(kwargs[key])
        self.slope = []
        self.q = []

    def g_parameter(self):
        '''
        :param kwargs:
        data 0 : baseMVA
        data 1 : bus
        data 2 : branch
        data 3 : c
        data 4 : ppc
        data 5 : nbr
        '''
        baseMVA = self.data[0]
        bus = self.data[1]
        branch = self.data[2]
        c = self.data[3]
        pcc = int(self.data[4])
        nbr = self.data[5]

        nb = bus.shape[0]

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

        Xgg = XX#np.delete(XX, 0, axis=0)
        Xgg = XX#np.delete(Xgg, 0, axis=1)

        bus_i = []
        for j in range(nb):
            bus_i.append(bus[j][BUS_I])

        diff = list(set(bus_i)-set(c))
        # print(diff)

        Xgg = np.delete(Xgg, diff, axis=0)
        Xgg = np.delete(Xgg, diff, axis=1)

        # print(Xgg)

        G = np.linalg.inv((np.matrix(np.imag(Xgg))))
        # print("G",(G))

        return G, Xgg

    