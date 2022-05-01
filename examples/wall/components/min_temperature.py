from __future__ import annotations
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from hubit.utils import ReadOnlyDict


def main(_input: ReadOnlyDict, results: Dict):
    """
    Find minimum temperature in the service layer excluding segments with a type
    in "no_service_segment_types". The segment types that are
    excluded is set in the input rendering the implementation more stable.

    The definition of the service layer as being the interface between the
    outermost and second outermost wall layer is controlled by the model and
    the component is unaware of the choice.
    """
    service_layer_min_temps = _input["service_layer_minimum_temperatures"]
    segment_types = _input["segment_types"]
    no_service_segment_types = _input["no_service_segment_types"]

    service_layer_min_temp = min(
        min_temp
        for segment_type, min_temp in zip(segment_types, service_layer_min_temps)
        if not (segment_type in no_service_segment_types)
    )

    results["service_layer_minimum_temperature"] = service_layer_min_temp


def version():
    return 1.0
