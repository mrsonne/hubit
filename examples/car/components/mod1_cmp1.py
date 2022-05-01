from time import sleep
from typing import Dict

from hubit.utils import ReadOnlyDict
from shared import PRICE_FOR_NAME


def main(_input: ReadOnlyDict, results: Dict):
    counts = _input["part_counts"]
    names = _input["part_names"]

    unit_prices = [PRICE_FOR_NAME[name] for name in names]

    result = sum([count * unit_price for count, unit_price in zip(counts, unit_prices)])

    # Delay to see the effect of worker caching.
    # If too fast the watcher loop will not update the results before all calcs are done
    sleep(0.1)
    results["car_price"] = result


def version():
    return "1.0.0"
