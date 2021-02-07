# density in kg/m^3
densities = {'brick': 2000.,
             'concrete': 2400.,
             'air': 0.,
             'styrofoam': 25.,
             'glasswool': 16.,
             'rockwool': 40.}


def weight(_input_consumed, _results_consumed, results_provided):
      """Calculate weight"""
      results_provided["weight"] = (_results_consumed["volume"]*
                                    densities[_input_consumed["material"]]) 

