import time

# USD / kg
prices = {'brick': 2000.,
          'concrete': 2400.,
          'air': 0.,
          'styrofoam': 25.,
          'glasswool': 16.,
          'rockwool': 40.}

def cost(_input_consumed, _results_consumed, results_provided):
    """
    """
    cost = sum([weight*prices[material] 
                for weight, material 
                in zip(_results_consumed["weights"], _input_consumed["materials"])])
    results_provided["cost"] = cost
    

def version():
    return 1.0