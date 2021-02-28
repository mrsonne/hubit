def car_price(_input_consumed, _results_consumed, results_provided):
    results_provided["car_price"] = sum(_results_consumed["prices"])
