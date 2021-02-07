from time import sleep
# thermal conductivities in W/m/K
ks = {'brick': 0.47,
      'concrete': 1.1,
      'air': 0.025,
      'styrofoam': 0.033,
      'glasswool': 0.030,
      'rockwool': 0.032}

def thermal_conductivity(_input_consumed, _results_consumed, results_provided):
      """Use 'material' in the input to compute the corresponding thermal
      conductivity. Use sleep to simulate some latency 
      """
      sleep(2.)
      results_provided["k_therm"] = ks[ _input_consumed["material"] ]

