from typing import Dict

from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    results["u"] = _input["u_tm1"] + _input["u_pm1"] / (
        _input["delta_x"] / _input["delta_t"] + _input["v"]
    )
