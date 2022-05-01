# density in kg/m^3
from typing import Dict

from hubit.utils import ReadOnlyDict


densities = {
    "brick": 2000.0,
    "concrete": 1835.0,
    "air": 0.0,
    "EPS": 25.0,
    "glasswool": 11.0,
    "rockwool": 60.0,
    "glass": 2200.0,
}


def weight(_input: ReadOnlyDict, results: Dict):
    """Calculate weight"""
    results["weight"] = _input["volume"] * densities[_input["material"]]
