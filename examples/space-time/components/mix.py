from typing import Dict
from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    liq_concs = _input["liq_concs"]
    V_liq = _input["V_liq"]
    results["mole_numbers"] = [conc * V_liq for conc in liq_concs]
