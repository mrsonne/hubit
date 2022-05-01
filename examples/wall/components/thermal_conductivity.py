from time import sleep
from typing import Dict

from hubit.utils import ReadOnlyDict

# thermal conductivities in W/m/K
ks = {
    "brick": 0.47,
    "concrete": 1.1,
    "air": 0.025,
    "EPS": 0.033,
    "glasswool": 0.030,
    "rockwool": 0.034,
    "glass": 0.8,
}


def thermal_conductivity(_input: ReadOnlyDict, results: Dict):
    """Use 'material' in the input to compute the corresponding thermal
    conductivity. Use sleep to simulate some latency
    """
    sleep(2.0)
    results["k_therm"] = ks[_input["material"]]
