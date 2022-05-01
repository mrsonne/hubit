from typing import Dict

from hubit.utils import ReadOnlyDict


def total_wall_cost(_input: ReadOnlyDict, results: Dict):
    """ """
    results["cost"] = sum(_input["segment_costs"])


def version():
    return 1.0
