from typing import Dict
from hubit.utils import ReadOnlyDict


def main(_input_consumed: ReadOnlyDict, results_provided: Dict):
    """
    Finds the equilibrium for the dissolution of A from a liquid (l) into a solid
    (s) phase.

    A(l) ⇌ A(s)

    c_s / c_l = k_eq

               A(l)        ⇌       A(s)
    start   n_tot                   0
    eq      n_tot - x               x

    Inserting into the equilibrium relation gives

    x / (n_tot - x) = k_eq * V_s / V_l

    and therefore

    x = (n_tot * k_eq * V_s / V_l) / (1 + k_eq * V_s / V_l)

    For multiple components A each equilibrium is assumed to be independent.
    """
    tot_composition = _input_consumed["tot_composition"]
    k_eq = _input_consumed["cell"]["k_eq"]
    V_solid = _input_consumed["cell"]["V_solid"]

    results_provided["liq_composition"] = 1
    results_provided["sol_composition"] = 1
    results_provided["V_liq"] = 1
