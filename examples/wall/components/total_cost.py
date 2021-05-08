def total_wall_cost(_input_consumed, _results_consumed, results_provided):
    """ """
    results_provided["cost"] = sum(_results_consumed["segment_costs"])


def version():
    return 1.0
