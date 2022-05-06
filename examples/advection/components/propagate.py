from typing import Dict

from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    beta = _input["v"] * _input["delta_t"] / _input["delta_x"]
    results["u"] = (_input["u_tm1"] + beta * _input["u_pm1"]) / (1 + beta)
