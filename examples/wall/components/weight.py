# density in kg/m^3
densities = {'brick': 2000.,
             'concrete': 1835., 
             'air': 0.,
             'EPS': 25.,
             'glasswool': 11.,
             'rockwool': 60.,
             'glass': 2200.
            }


def weight(_input_consumed, _results_consumed, results_provided):
      """Calculate weight"""
      results_provided["weight"] = (_results_consumed["volume"]*
                                    densities[_input_consumed["material"]]) 

