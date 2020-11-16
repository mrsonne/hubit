from time import sleep
ks = {'pvdf': 0.23, 'xlpe': 0.3, 'hdpe': 0.22, 'pa11': 0.24}

def thermal_conductivity(_input_consumed, _results_consumed, results_provided):
    sleep(2.)
    print("thermal_conductivity", "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    print _input_consumed
#    results_provided["ktherm"] = [ks[_input_consumed["materials"]] ]
    print [ks[material] for material in _input_consumed["materials"]]
    results_provided["ks_walls"] = [ks[material] for material in _input_consumed["materials"]]

