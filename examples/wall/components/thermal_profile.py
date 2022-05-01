import time
from typing import Dict

from hubit.utils import ReadOnlyDict


def thermal_prof(_input: ReadOnlyDict, results: Dict):
    """Use thermal conductivities, thicknesses and boundary conditions
    to compute the corresponding thermal profile and heath flux in a
    flat multi layer wall. Use sleep to simulate some latency.
    The component doesn't use numpy to avoid dependencies the are
    not necessary for the the example.
    """

    # Simulate latency
    time.sleep(0.25)

    # Get data consumed
    # thickness = x2 - x1 > 0
    thicknesses = _input["thicknesses"]
    ks = _input["ks_walls"]
    T_in = _input["temp_in"]
    T_out = _input["temp_out"]

    # Calculate total thermal resistance and overall heat transfer number
    Rs = [t / k for (k, t) in zip(ks, thicknesses)]
    R_tot = sum(Rs)
    htn = 1.0 / R_tot

    # Calculate heat flux [J/s/m^2]
    q = -(T_out - T_in) * htn

    # Calculate temperature changes in the positive direction
    temp_changes = [-q * R for R in Rs]

    # Calculate temperature on the outside of the layers
    T_outer_all_layers = [T_in + temp_changes[0]]
    for temp_change in temp_changes[1:]:
        T_outer_all_layers.append(T_outer_all_layers[-1] + temp_change)

    results["outer_temperature_all_layers"] = T_outer_all_layers
    results["heat_flux"] = q
    results["heat_transfer_number"] = htn


def version():
    return 1.0
