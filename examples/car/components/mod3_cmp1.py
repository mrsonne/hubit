import shared


def part_price(_input_consumed, results_provided):
    counts = _input_consumed["parts_count"]
    names = _input_consumed["parts_name"]
    results_provided["parts_price"] = [
        count * shared.PRICE_FOR_NAME[name] for count, name in zip(counts, names)
    ]


def version():
    return "0.1.1"
