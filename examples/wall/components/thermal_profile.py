"""
The component doesn't use numpy to avoid dependencies 
the are not necessary for the the example
"""

import time

def thermal_prof(_input_consumed, _results_consumed, results_provided):
    # Simulate latency
    time.sleep(0.25)

    # Get data consumed
    thicknesses = _input_consumed["thicknesses"]
    ks = _results_consumed["ks_walls"]
    T_in = _input_consumed["temp_in"]
    T_out = _input_consumed["temp_out"]

    # Calculate total thermal resitance
    Rs = [t/k for (k, t) in zip(ks, thicknesses)]
    R_tot = sum(Rs)

    # Calculate heat flux [J/s/m^2]
    q = ( T_out - T_in ) / R_tot

    # Calculate temperature drops
    temp_drops = [ q*R for R in Rs ]

    # Calculate temperature on the outside of the layers
    T_layer_outer =  [T_in + temp_drops[0]]
    for temp_drop in temp_drops[1:]:
        T_layer_outer.append(T_layer_outer[-1] + temp_drop)

    results_provided["outer_temperature_all_layers"] = T_layer_outer
    results_provided["heat_flux"] = q

def version():
    return 1.0