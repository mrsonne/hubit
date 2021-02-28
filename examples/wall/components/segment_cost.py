import time

KG_PER_LBS = 0.453592

# USD / kg
prices = {
    "brick": 1.1
    / (
        4.6 * KG_PER_LBS
    ),  # https://www.homedepot.com/p/7-5-8-in-x-2-1-4-in-x-3-5-8-in-Clay-Brick-20050941/100676108?MERCH=REC-_-pip_alternatives-_-100323015-_-100676108-_-N
    "concrete": 1.7
    / (
        33 * KG_PER_LBS
    ),  # https://www.homedepot.com/p/16-in-x-8-in-x-4-in-Normal-Weight-Concrete-Block-Solid-H0408160003000000/312064973?MERCH=REC-_-pip_alternatives-_-202535931-_-312064973-_-N
    "air": 0.0,
    "EPS": 8.45
    / 6.0
    / (
        2.0 * KG_PER_LBS
    ),  # https://www.homedepot.com/p/3-4-in-x-1-25-ft-x-4-ft-R-2-65-Polystyrene-Panel-Insulation-Sheathing-6-Pack-150705/202090272
    "glasswool": 35.0 / (17.1 * KG_PER_LBS),
    "rockwool": 621.0
    / 12.0
    / (
        36.8 * KG_PER_LBS
    ),  # https://www.homedepot.com/p/ROCKWOOL-R-30-ComfortBatt-Fire-Resistant-Mineral-Wool-Insulation-Batt-15-in-x-47-in-12-bag-RXCB301525/205972559
}


def cost(_input_consumed, _results_consumed, results_provided):
    """"""
    if _input_consumed["type"] == "window":
        # A window has a fixed price
        cost = 1000.0
    else:
        # Cost based on weight
        cost = sum(
            [
                weight * prices[material]
                for weight, material in zip(
                    _results_consumed["weights"], _input_consumed["materials"]
                )
            ]
        )
    results_provided["cost"] = cost


def version():
    return 1.0
