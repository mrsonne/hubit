from time import sleep


def main(_input_consumed, _results_consumed, results_provided):
    tank_parameters = _input_consumed["tank_parameters"]

    # Either the inlet flow is found in the input (first tank) or
    # in the results (subsequent tanks)
    try:
        vol_inlet_flow = _input_consumed["vol_inlet_flow"]
    except KeyError:
        vol_inlet_flow = _results_consumed["vol_inlet_flow"]

    results_provided["vol_outlet_flow"] = (
        tank_parameters["orifice_area"] * vol_inlet_flow
    )
    results_provided["vol_over_flow"] = 12.0


def version():
    return "1.0.0"
