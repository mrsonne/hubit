from typing import Dict

from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    results["u"] = _input["u"]
    results["t"] = _input["t"]
