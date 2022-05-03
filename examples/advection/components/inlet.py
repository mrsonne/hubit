from typing import Dict

from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    wavelet_pars = _input["wavelet_pars"]
    t = _input["t_prev"] + _input["delta_t"]
    results["u"] = 1
    results["t"] = t
