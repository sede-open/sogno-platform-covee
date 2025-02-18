import control_strategies.linear_control as linear_control
from control_strategies.runPF import runPF
import numpy as np

class Linear_Control():

    def __init__(self, grid_data):
        self.grid_data = grid_data	

        self.control_reactive_power = linear_control.Linear_Reactive_Power(grid_data)
        [self.reactive_power,self.X] = self.control_reactive_power.initialize_control()

        self.control_active_power_PV = linear_control.Linear_Active_Power_PV(grid_data)
        self.active_power_PV = self.control_active_power_PV.initialize_control()

        self.num_PV = self.grid_data[7]
        self.num_bus = self.grid_data[4]


    def control_(self, k, PV_list, q_PV, v_gen, active_power_PV):

        self.reactive_power = q_PV
        self.active_power_PV = active_power_PV

        # REACTIVE POWER CONTROL PV
        # ================================================================================================
        self.reactive_power = self.control_reactive_power.Voltage_Control(k, PV_list, q_PV, v_gen)

        # REACTIVE POWER CONTROL PV
        # ================================================================================================
        # self.active_power_PV = self.control_active_power_PV.Voltage_Control(k, PV_list, active_power_PV, v_gen)

        return self.reactive_power, self.active_power_PV
