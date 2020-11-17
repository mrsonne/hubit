from time import sleep
ks = {'pvdf': 0.23, 'xlpe': 0.3, 'hdpe': 0.22, 'pa11': 0.24}

def thermal_conductivity(_input_consumed, _results_consumed, results_provided):
    sleep(2.)
    # print("thermal_conductivity", "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    # print _input_consumed, ks[ _input_consumed["material"] ]
    results_provided["k_therm"] = ks[ _input_consumed["material"] ]

