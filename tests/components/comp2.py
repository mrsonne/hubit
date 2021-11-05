def multiply_by_factors(_input_consumed, results_provided):
    temperatures = [
        factor * number
        for number, factor in zip(
            _input_consumed["numbers_provided_by_comp1"], _input_consumed["factors"]
        )
    ]
    results_provided["temperatures"] = temperatures
