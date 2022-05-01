from __future__ import annotations
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):

    yield_fraction = _input["yield_fraction"]
    Q_in = _input["Q_in"]
    Q_transfer = [val for key, val in _input.items() if "Q_transfer" in key]
    results["Q_yield"] = yield_fraction * (sum(Q_transfer) + Q_in)


def version() -> str:
    return "1.0.0"
