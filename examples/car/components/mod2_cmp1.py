import shared


def part_price(_input_consumed, _results_consumed, results_provided):
    count = _input_consumed["part_count"]
    name = _input_consumed["part_name"]
    results_provided["part_price"] = count * shared.PRICE_FOR_NAME[name]


def version():
    return "1.3.1"
