from __future__ import annotations
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from hubit.utils import ReadOnlyDict


def main(_input_consumed: ReadOnlyDict, results_provided: Dict):

    tank_parameters = _input_consumed["tank_parameters"]
    vol_inlet_flow = _input_consumed["vol_inlet_flow"]

    results_provided["vol_outlet_flow"] = (
        tank_parameters["orifice_area"] * vol_inlet_flow
    )
    results_provided["vol_over_flow"] = 12.0


def version() -> str:
    return "1.0.0"
