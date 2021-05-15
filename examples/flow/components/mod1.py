from time import sleep


def main(_input_consumed, _results_consumed, results_provided):
    results_provided["inflow"] = (
        _input_consumed["total_flow"] * _input_consumed["fraction"]
    )


def version():
    return "1.0.0"
