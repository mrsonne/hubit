import math
from typing import Dict

from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    pars = _input["wavelet_pars"]
    t = _input["t_prev"] + _input["delta_t"]
    results["u"] = pars["a"]
    results["u"] *= math.exp(-((t - pars["t_mean"]) ** 2) / (2 * pars["s"] ** 2))
    results["t"] = t
