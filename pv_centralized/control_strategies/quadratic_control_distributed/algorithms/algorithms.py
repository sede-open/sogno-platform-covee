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
        diff = [int(i) for i in diff]

        Xgg = np.delete(Xgg, diff, axis=0)
        Xgg = np.delete(Xgg, diff, axis=1)

        # print(Xgg)

        G = np.linalg.inv((np.matrix(np.imag(Xgg))))
        # print("G",(G))

        return G, Xgg

    def network_compensation(self):
        '''
        :param kwargs:
        data 0 : lambda_max
        data 1 : lambda_min
        data 2 : alpha
        data 3 : voltage value
        data 4 : VMAX
        data 5 : VMIN
        data 6 : num gen
        data 7 : delta_t
        '''

        lamda_max = self.data[0]
        lamda_min = self.data[1]
        alpha = self.data[2]
        v = self.data[3]
        VMAX = self.data[4]
        VMIN = self.data[5]
        ng = int(self.data[6])
        delta_t = self.data[7]

        for i in range(ng):
            lamda_max[i] = max(lamda_max[i]*delta_t-alpha[i]*(-v[i]+VMAX[i]),0)
            lamda_min[i] = max(lamda_min[i]*delta_t-alpha[i]*(v[i]-VMIN[i]),0)

        return lamda_max, lamda_min


    def inner_loop(self):
        '''
        :param kwargs:
        data 0 : lambda_max
        data 1 : lambda_min
        data 2 : K
        data 3 : mu_min
        data 4 : mu_max
        data 5 ; gamma
        data 6 : G
        data 7 : QMIN
        data 8 : QMAX
        data 9 : ng
        data 10 : qhat_pre
        data 11 : delta_t
        data 12 : X
        '''

        lamda_max = np.array(self.data[0])
        lamda_min = np.array(self.data[1])
        K = self.data[2]
        mu_min = np.array(self.data[3])
        mu_max = np.array(self.data[4])
        gamma = self.data[5]
        G =self.data[6]
        QMIN = np.array(self.data[7])
        QMAX = np.array(self.data[8])
        ng = int(self.data[9])
        qhat = np.array([0.01]*ng)
        qhat_pre = np.array([0.01]*ng)
        delta_t = self.data[11]
        X = self.data[12]
        
        mu_min_old = np.array(self.data[3])
        mu_max_old = np.array(self.data[4])

        for i in range(len(mu_min)):
            for j in range(K):
                mu_min[i] = np.amax((mu_min[i]*delta_t+gamma*(QMIN[i]-qhat_pre[i]),0))
                mu_max[i] = np.amax((mu_max[i]*delta_t+gamma*(-QMAX[i]+qhat_pre[i]),0))
                mu_min_tot = np.hstack([mu_min_old[0:i],mu_min[i],mu_min_old[(i+1):len(mu_min_old)]])
                mu_max_tot = np.hstack([mu_max_old[0:i],mu_max[i],mu_max_old[(i+1):len(mu_max_old)]])
                qhat_pre[i] = (np.array((np.matrix(np.imag(X))*np.matrix(G))[i,:]*np.transpose(np.matrix(lamda_min-lamda_max))).flatten()
                            + np.array(np.matrix(G)[i,:]*np.transpose(np.matrix(mu_min_tot-mu_max_tot))).flatten())

        qhat = np.maximum(qhat_pre,QMIN)
        qhat = np.minimum(qhat, QMAX)

        return qhat.tolist(), mu_min.tolist(), mu_max.tolist()

    def static(self):
        '''
        :param kwargs:
        data 0 : voltage value
        data 1 : q
        data 2 : Vmax
        data 3 : Vmax2
        data 4 : Qmin
        data 5 : num gen
        '''
        v = self.data[0]
        self.q = self.data[1]
        VMAX = self.data[2]
        VMAX2 = self.data[3]
        QMIN = self.data[4]
        ng = int(self.data[5])
        slope = [0.0]*ng
        for i in range(ng):
            slope[i] = (v[i]-VMAX2[i])*1*((-QMIN[i])/(VMAX[i]-VMAX2[i]))
            self.q[i] = min(-(min(slope[i], -QMIN[i])),0)

        return self.q

    def localincremental(self):
        '''
        :param kwargs:
        data 0 : voltage value
        data 1 : q
        data 2 : Vmax
        data 3 : Qmin
        data 4 : num gen
        data 5 : VMAX2
        '''
        v = self.data[0]
        self.q = self.data[1]
        VMAX = self.data[2]
        QMIN = self.data[3]
        ng = int(self.data[4])
        VMAX2 = self.data[5]
        for i in range(ng):
            if abs(v[i] - VMAX[i]) >= abs(v[i]-VMAX2[i]):
                self.q[i]= 0.0  
            else:
                self.q[i] = self.q[i] - max((v[i] - VMAX[i]), 0)
                self.q[i] = max(self.q[i], QMIN[i])

        return self.q



# For Test
# =============================================================
# if __name__ == "__main__":
#     test = algorithms(v=1, VMAX=np.asarray([1,4]), VMAX2 = np.asarray([2,3]), QMIN = 4)
#     test.Gparameter()
#     print(test.Y)



