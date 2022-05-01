# Calculate heat flow from width, height and heat flux


from typing import Dict

from hubit.utils import ReadOnlyDict


def heat_flow(_input: ReadOnlyDict, results: Dict):
    area = _input["width"] * _input["height"]
    results["heat_flow"] = _input["heat_flux"] * area
