from time import sleep
from typing import Dict

from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    """
    car price
    """
    # sleep(0.5)
    results["car_price"] = sum(_input["prices"])
