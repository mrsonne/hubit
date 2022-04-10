from typing import Dict
from hubit.utils import ReadOnlyDict


def get_change(n, k_eq, V_s, V_l):
    return (n * k_eq * V_s / V_l) / (1 + k_eq * V_s / V_l)


def main(_input: ReadOnlyDict, results: Dict):
    """
    Finds the equilibrium for the dissolution of A from a liquid (l) into a solid
    (s) phase.

    A(l) ⇌ A(s)

    At equilibrium the following relation is fulfilled

    c_s / c_l = k_eq

    where c_s and c_l are the concentrations of A in the solid and
    liquid phases, respectively. When the total amount of A is n the
    equilibrium can be illustrated as

               A(l)        ⇌       A(s)
    start       n                   0
    eq        n - x                 x

    When the volume of the solid and liquid phase are V_s and V_l, respectively,
    the equilibrium relation may be written

    x / (n - x) = k_eq * V_s / V_l.

    Therefore, x may be written

    x = (n * k_eq * V_s / V_l) / (1 + k_eq * V_s / V_l)

    For multiple components, each equilibrium is assumed to be independent.
    """
    n = _input["mole_numbers"]
    k_eq = _input["cell"]["k_eq"]
    V_solid = _input["cell"]["V_solid"]
    V_liq = _input["V_liq"]
    xs = [get_change(_n, _k_eq, V_solid, V_liq) for _n, _k_eq in zip(n, k_eq)]
    results["liq_composition"] = [_n - _x for _x, _n in zip(xs, n)]
    results["sol_composition"] = xs
    results["V_liq"] = V_liq
