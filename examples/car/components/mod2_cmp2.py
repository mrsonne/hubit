from time import sleep


def main(_input_consumed, results_provided):
    """
    car price
    """
    # sleep(0.5)
    results_provided["car_price"] = sum(_input_consumed["prices"])
