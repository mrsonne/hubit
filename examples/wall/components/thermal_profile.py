
import time
# import multiprocessing

def thermal_prof(_input_consumed, _results_consumed, results_provided):
    # p = multiprocessing.current_process()
    # print 'workerfun_thermal:', p.name, p.pid
    # ks = _results_consumed["ktherm"]
    ks = _results_consumed["ks_walls"]
    t_in = _input_consumed["temp_in"]
    t_out = _input_consumed["temp_out"]
    thicknesses = _input_consumed["thicknesses"]
    print('thicknesses thicknesses thicknesses thicknesses', thicknesses)
    time.sleep(0.25)
    results_provided["temperatures_all_layers"] = [1, 2, 3]
    results_provided["heat_flows_all_layers"] = [4, 5, 6]

def version():
    return 1.0