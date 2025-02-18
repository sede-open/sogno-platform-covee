import numpy as np
from pypower.makeYbus import makeYbus
from pypower.idx_bus import BUS_I
from scipy.sparse import csr_matrix

class algorithms_controllable_loads:

    def __init__(self, **kwargs):
        self.data = []
        for key in kwargs:
            self.data.append(kwargs[key])
        self.slope = []
        self.pL = []

    def g_parameter(self):
        '''
        :param kwargs:
        data 0 : baseMVA
        data 1 : bus
        data 2 : branch
        data 3 : c
        data 4 : ppc
        data 5 : nbr
        data 6 : node_batteries
        '''
        baseMVA = self.data[0]
        bus = self.data[1]
        branch = self.data[2]
        c = self.data[3]
        pcc = int(self.data[4])
        nbr = self.data[5]
        n_battery = self.data[6]

        nb = bus.shape[0]

        Ybus = makeYbus(baseMVA, bus, branch)[0]
        Ybus = Ybus.todense()

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
        # print("Xgg pre", np.shape(Xgg))

        diff = list(set(bus_i)-set(n_battery))
        # print("diff", diff)

        Xgg = np.delete(Xgg, diff, axis=0)
        Xgg = np.delete(Xgg, diff, axis=1)
        # print("Xgg post", np.shape(Xgg))

        G = np.linalg.inv((np.matrix(np.real(Xgg))))
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
        data 5 : VMAX
        data 6 : node_batteries
        data 7 : delta_t
        '''

        lamda_max = self.data[0]
        lamda_min = self.data[1]
        alpha = self.data[2]
        v = self.data[3]
        VMAX = self.data[4]
        VMIN = self.data[5]
        n_battery = self.data[6]
        delta_t = self.data[7]

        for i in range(len(n_battery)):
            lamda_max[i] = max(lamda_max[i]-alpha[i]*(-v[i]+VMAX[i]),0)
            lamda_min[i] = max(lamda_min[i]-alpha[i]*(v[i]-VMIN[i]),0)

        return lamda_max, lamda_min


    def inner_loop(self):
        '''
        :param kwargs:
        data 0 : lambda_max
        data 1 : lambda_min
        data 2 : K
        data 3 : xi_max
        data 4 : xi_min
        data 5 : gamma
        data 6 : G
        data 7 : PMAX
        data 8 : PMIN
        data 9 : node_batteries
        data 10 : phat_pre
        data 11 : delta_t
        data 12 : X
        '''

        lamda_max = np.array(self.data[0])
        lamda_min = np.array(self.data[1])
        K = self.data[2]
        xi_min = np.array(self.data[3])
        xi_max = np.array(self.data[4])
        gamma = self.data[5]
        G =self.data[6]
        PMAX = np.array(self.data[7])
        PMIN = np.array(self.data[8])
        n_battery = (self.data[9])
        phat = np.array([0.01]*len(n_battery))
        phat_pre = np.array([0.01]*len(n_battery))
        delta_t = self.data[11]
        X = self.data[12]

        xi_min_old = np.array(self.data[3])
        xi_max_old = np.array(self.data[4])

        for i in range(len(xi_min)):
            for j in range(K):
                xi_min[i] = np.amax((xi_min[i]+gamma*(PMIN[i]-phat_pre[i]),0))
                xi_max[i] = np.amax((xi_max[i]+gamma*(-PMAX[i]+phat_pre[i]),0))
                xi_min_tot = np.hstack([xi_min_old[0:i],xi_min[i],xi_min_old[(i+1):len(xi_min_old)]])
                xi_max_tot = np.hstack([xi_max_old[0:i],xi_max[i],xi_max_old[(i+1):len(xi_max_old)]])
                phat_pre[i] = (np.array((np.matrix(np.real(X))*np.matrix(G))[i,:]*np.transpose(np.matrix(lamda_min-lamda_max))).flatten()
                            + np.array(np.matrix(G)[i,:]*np.transpose(np.matrix(xi_min_tot-xi_max_tot))).flatten())

            phat = np.maximum(phat_pre,PMIN)
            phat = np.minimum(phat, PMAX)

        return phat.tolist(), xi_max.tolist(), xi_min.tolist()



















# For Test
# =============================================================
# if __name__ == "__main__":
#     test = algorithms(v=1, VMAX=np.asarray([1,4]), VMAX2 = np.asarray([2,3]), QMIN = 4)
#     test.Gparameter()
#     print(test.Y)



