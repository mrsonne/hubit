from __future__ import annotations
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    unit_price = _input["unit_price"]
    Q_yield = _input["Q_yield"]
    results["revenue"] = Q_yield * unit_price


def version() -> str:
    return "2.0.0"
