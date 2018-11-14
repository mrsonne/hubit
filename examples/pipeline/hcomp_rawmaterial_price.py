from time import sleep
import os

# Option 1: Make examples folder into a package (requires __init__.py in examples folder)
# from examples.dependency import CalculationClass

# Option 2: Append to sys.path
# import sys
# THISPATH = os.path.dirname(os.path.abspath(__file__))
# sys.path.insert(0, THISPATH)
# from dependency import CalculationClass

# Option 3: 
import imp
THISPATH = os.path.dirname(os.path.abspath(__file__))
filename = "dependency"
f, _filename, description = imp.find_module(filename, [THISPATH])
module = imp.load_module(filename, f, _filename, description)
CalculationClass = getattr(module, "CalculationClass")


def rawmaterial_price(_input_consumed, _results_consumed, results_provided):
    
    print("workerfun_price")
    cc = CalculationClass()
    sleep(1.5)
    mats = _input_consumed["materials"]
    ts = _input_consumed["thicknesses"]
    ods = _input_consumed["odias"]
    lengths = _input_consumed["lengths"]
    nsegs = len(lengths)
    price = sum([cc.price_seg(mats[iseg], ts[iseg], ods[iseg], lengths[iseg]) for iseg in range(nsegs)])
    results_provided["price_tot"] = price


def version():
    return 2.2