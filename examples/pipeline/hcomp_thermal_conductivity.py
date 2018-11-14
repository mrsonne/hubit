from time import sleep
ks = {'pvdf': 0.23, 'xlpe': 0.3, 'hdpe': 0.22, 'pa11': 0.24}

def thermal_conductivity(_input_consumed, _results_consumed, results_provided):
    sleep(2.)
    print("workerfun_thermal")
    results_provided["ks_walls"] = [ks[mat] for mat in _input_consumed["materials"]]

