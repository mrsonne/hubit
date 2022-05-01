from typing import Dict
from hubit.utils import ReadOnlyDict
import shared


def part_price(_input: ReadOnlyDict, results: Dict):
    counts = _input["parts_count"]
    names = _input["parts_name"]
    results["parts_price"] = [
        count * shared.PRICE_FOR_NAME[name] for count, name in zip(counts, names)
    ]


def version():
    return "0.1.1"
