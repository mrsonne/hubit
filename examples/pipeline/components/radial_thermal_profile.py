
import time
# import multiprocessing

def radial_thermal_prof(_input_consumed, _results_consumed, results_provided):
    # p = multiprocessing.current_process()
    # print 'workerfun_thermal:', p.name, p.pid
    # ks = _results_consumed["ktherm"]
    ks = _results_consumed["ks_walls"]
    tb = _input_consumed["temp_bore"]
    to = _input_consumed["temp_out"]
    time.sleep(0.25)
    results_provided["temperatures_all_layers"] = [1, 2, 3]
    results_provided["heat_flows_all_layers"] = [4, 5, 6]

def version():
    return 1.0