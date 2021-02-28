# density in kg/m^3
densities = {
    "brick": 2000.0,
    "concrete": 1835.0,
    "air": 0.0,
    "EPS": 25.0,
    "glasswool": 11.0,
    "rockwool": 60.0,
    "glass": 2200.0,
}


def weight(_input_consumed, _results_consumed, results_provided):
    """Calculate weight"""
    results_provided["weight"] = (
        _results_consumed["volume"] * densities[_input_consumed["material"]]
    )
