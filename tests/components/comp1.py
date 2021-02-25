def multiply_by_2(_input_consumed, _results_consumed, results_provided):
    results = [2*x for x in _input_consumed["numbers_consumed_by_comp1"]]
    results_provided["comp1_results"] = results
