from typing import Dict
from hubit.utils import ReadOnlyDict


def main(_input_consumed: ReadOnlyDict, results_provided: Dict):
    tot_composition = _input_consumed["tot_composition"]
    k_eq = _input_consumed["cell"]["k_eq"]
    V_solid = _input_consumed["cell"]["V_solid"]

    results_provided["liq_composition"] = 1
    results_provided["sol_composition"] = 1
    results_provided["V_liq"] = 1
