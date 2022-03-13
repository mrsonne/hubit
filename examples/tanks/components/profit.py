from __future__ import annotations
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from hubit.utils import ReadOnlyDict


def main(_input_consumed: ReadOnlyDict, results_provided: Dict):
    unit_price = _input_consumed["unit_price"]
    Q_yield = _input_consumed["Q_yield"]
    results_provided["revenue"] = Q_yield * unit_price


def version() -> str:
    return "2.0.0"
