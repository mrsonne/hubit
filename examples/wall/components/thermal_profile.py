"""
The component doesn't use numpy to avoid dependencies 
the are not necessary for the the example
"""

import time

def thermal_prof(_input_consumed, _results_consumed, results_provided):
    # Simulate latency
    time.sleep(0.25)

    # Get data consumed
    # thickness = x2 - x1 > 0
    thicknesses = _input_consumed["thicknesses"]
    ks = _results_consumed["ks_walls"]
    T_in = _input_consumed["temp_in"]
    T_out = _input_consumed["temp_out"]

    # Calculate total thermal resistance
    Rs = [t/k for (k, t) in zip(ks, thicknesses)]
    R_tot = sum(Rs)

    # Calculate heat flux [J/s/m^2]
    q = - ( T_out - T_in ) / R_tot

    # Calculate temperature changes in the positive direction 
    temp_changes = [ -q*R for R in Rs ]

    # Calculate temperature on the outside of the layers
    T_outer_all_layers =  [T_in + temp_changes[0]]
    for temp_change in temp_changes[1:]:
        T_outer_all_layers.append(T_outer_all_layers[-1] + temp_change)

    results_provided["outer_temperature_all_layers"] = T_outer_all_layers
    results_provided["heat_flux"] = q

def version():
    return 1.0