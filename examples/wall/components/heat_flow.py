# Calculate heat flow from width, height and heat flux


def heat_flow(_input_consumed, results_provided):
    area = _input_consumed["width"] * _input_consumed["height"]
    results_provided["heat_flow"] = _input_consumed["heat_flux"] * area
    return results_provided
