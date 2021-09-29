def total_wall_cost(_input_consumed, results_provided):
    """ """
    results_provided["cost"] = sum(_input_consumed["segment_costs"])


def version():
    return 1.0
