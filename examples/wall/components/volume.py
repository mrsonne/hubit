from typing import Dict

from hubit.utils import ReadOnlyDict


def volume(_input: ReadOnlyDict, results: Dict):
    """Calculate volume"""
    results["volume"] = _input["thickness"] * _input["width"] * _input["height"]
