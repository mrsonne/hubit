from time import sleep
from typing import Dict
from hubit.utils import ReadOnlyDict
import shared


def main(_input: ReadOnlyDict, results: Dict):
    """
    part price calculations
    """
    count = _input["part_count"]
    name = _input["part_name"]
    sleep(0.1)
    results["part_price"] = count * shared.PRICE_FOR_NAME[name]


def version():
    return "1.3.1"
