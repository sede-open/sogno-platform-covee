from pypower.api import *
from pypower.ext2int import ext2int
from pypower.idx_brch import F_BUS, T_BUS, TAP, BR_R, BR_X, BR_B, RATE_A, PF, QF, PT, QT
from pypower.idx_bus import BUS_I,BUS_TYPE, REF, PD, QD, VM, VA, VMAX, VMIN, NONE
from pypower.idx_gen import GEN_BUS, PG, QG, PMAX, PMIN, QMAX, QMIN, VG, GEN_STATUS
from pypower.int2ext import int2ext

from covee.powerflow.csv_files.read_profiles import read_profiles

from scipy.sparse import issparse, vstack, hstack, csr_matrix as sparse
from numpy import flatnonzero as find

import numpy as np
from pypower.ppoption import ppoption

from covee.powerflow.csv_files.read_profiles import read_profiles



class runPF_class():

    def __init__(self, active_nodes, active_ESS, full_nodes, total_nodes):
        self.active_nodes = active_nodes
        self.active_ESS = active_ESS
        self.full_nodes = full_nodes
        self.total_nodes = total_nodes

    def read_profiles(self, conf_dict, grid_data):
        profile_out = {}
        # read profiles from CSV files
        # =======================================================================
        profiles = read_profiles(conf_dict, grid_data)
        [PV_list, P_load_list] = profiles.read_csv()

        profile_out = {"gen_profile" : PV_list,"load_profile": P_load_list}

        return profile_out

    def initialize(self, name, profiles):
        # Input Data
        # =============================================================
        ppc = name
        pvproduction = profiles[0]
        demandprofile_P = profiles[1]

        bt = ppc["bus"][:, 1]

        ## determine which buses, branches, gens are connected and
        ## in-service
        nb = ppc["bus"].shape[0]
        n2i = sparse((range(nb), (ppc["bus"][:, BUS_I], np.zeros(nb))),
                        shape=(max(ppc["bus"][:, BUS_I].astype(int)) + 1, 1))
        n2i = np.array( n2i.todense().flatten() )[0, :] # as 1D array
        bs = (bt != NONE)                               ## bus status
        gs = ( (ppc["gen"][:, GEN_STATUS] > 0) &          ## gen status
                bs[ n2i[ppc["gen"][:, GEN_BUS].astype(int)] ] )
        ppc = ext2int(ppc)      # convert to continuous indexing starting from 0
        BUS_TYPE = 1

        # Gather information about the system
        # =============================================================
        baseMVA, bus, gen, branch = \
            ppc["baseMVA"], ppc["bus"], ppc["gen"], ppc["branch"]

        nb = bus.shape[0]                        # number of buses
        ng = gen.shape[0]                        # number of generators
        nbr = branch.shape[0]                    # number of branches

        for i in range(int(nb)):
            if bus[i][BUS_TYPE] == 3.0:
                pcc = i
            else:
                pass     
        
        grid_data = {"baseMVA":baseMVA,"branch":branch,"pcc":pcc,"bus":bus,"gen":gen,"nb":nb,"ng":ng,"nbr":nbr}

        return grid_data

    def run_Power_Flow(self, ppc, active_power,reactive_power,active_power_ess,pv_profile,load_profile):
        ppc = ext2int(ppc)      # convert to continuous indexing starting from 0

        # Gather information about the system
        # =============================================================
        gen = ppc["gen"]

        nb = ppc["bus"].shape[0]                        # number of buses
        ng = gen.shape[0]                        # number of generators

        for i in range(1,ng):
            if gen[i][0] in self.active_nodes:
                pass
            else:
                np.delete(ppc["gen"],(i),axis=0)       

        #print("Number of Reactive Power Compensator = ",int(len(c)))

        ############## SET THE ACTUAL LOAD AND GEN VALUES ###############
        s = 0
        for i in range(nb):
            ppc["bus"][i][PD] = load_profile[i] 
            ppc["bus"][i][QD] = 0.0
            if self.active_ESS != None and (self.active_ESS == ppc["bus"][i][BUS_I]).any():
                ppc["bus"][i][PD] = load_profile[i]-active_power_ess[s]
                s +=1
        
        r = 0
        for j in range(ng):
            gen[j][PG] = 0.0
            gen[j][QG] = 0.0
            if (self.active_nodes == gen[j][GEN_BUS]).any():
                gen[j][QG] = reactive_power[r]
                gen[j][PG] = pv_profile[r]+active_power[r]
                r +=1
            else: 
                pass

        ppc['gen'] = gen
        ppc = int2ext(ppc)


        ############# RUN PF ########################
        opt = ppoption(VERBOSE=0, OUT_ALL=0, UT_SYS_SUM=0, PF_ALG = 3)
        results = runpf(ppc, opt)
        
        bus_results = results[0]['bus']
        v_gen = bus_results.T[VM][self.total_nodes].tolist()
        v_tot = bus_results.T[VM][self.full_nodes].tolist()
        v_pv = bus_results.T[VM][self.active_nodes].tolist()
        if self.active_ESS != None:
            v_ess = bus_results.T[VM][self.active_ESS].tolist()
        else:
            v_ess = []

        p = ppc['gen'].T[PG][1:(len(self.active_nodes)+1)].tolist()     # SUBI - something is wrong here
        p_load = ppc['bus'].T[PD][self.active_nodes].tolist()           # SUBI - something is wrong here
        
        return v_tot,v_gen,p, self.active_nodes, p_load, v_pv, v_ess