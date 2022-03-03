from pprint import pprint
import logging
from .shared import get_model
from hubit import clear_hubit_cache

# logging.basicConfig(level=logging.INFO)


def model_0():
    """Send entire car object to worker"""
    print(f"\n***MODEL 0***")
    hmodel = get_model("model0.yml")
    query = ["cars[0].price", "cars[1].price", "cars[2].price"]
    query = ["cars[-1].price", "cars[2].price"]
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print("response:", response)
    print("results: ", hmodel.results.as_dict())


def model_1():
    """Run model 1 and illustrate worker-level caching

    input.yml shows that cars[0] and cars[2] are identical so the effect
    of worker caching on the execution time can be seen. The execution time
    with worker caching is expected to be ~2/3 of the execution time without
    worker chaching (the calculation for one car can be reused).
    """
    print(f"\n***MODEL 1***")

    hmodel = get_model("model1.yml")
    query = ["cars[0].price", "cars[1].price", "cars[2].price"]

    # With worker caching
    hmodel.set_component_caching(True)
    response = hmodel.get(query, use_multi_processing=use_multi_processing)

    # Without worker caching
    hmodel.set_component_caching(False)
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    results = hmodel.results
    print("results", results)
    results_dict = results.as_dict()
    print("results_dict", results_dict)
    results_inflated = results.inflate()
    print("results_inflated", results_inflated)

    print(response)
    elapsed_times = hmodel.log().get_all("elapsed_time")
    print(f"Time WITH worker caching: {elapsed_times[1]:.1f} s. ")
    print(f"Time WITHOUT worker caching: {elapsed_times[0]:.1f} s. ")
    print(hmodel.log())


def model_2():
    """Run model 2 and illustrate model-level caching"""
    print(f"\n***MODEL 2***")
    model_caching_mode = "after_execution"
    # model_caching_mode = "incremental"
    # model_caching_mode = "never"

    clear_hubit_cache()
    hmodel = get_model("model2.yml")
    hmodel.set_model_caching(model_caching_mode)
    query = [
        "cars[:].parts[:].price",  # price for all components for all cars
        "cars[:].price",  # price for all cars
    ]
    response = hmodel.get(
        query, use_results="cached", use_multi_processing=use_multi_processing
    )
    response = hmodel.get(
        query, use_results="cached", use_multi_processing=use_multi_processing
    )
    pprint(response)
    elapsed_times = hmodel.log().get_all("elapsed_time")
    print(f"\nTime WITHOUT cached results on model: {elapsed_times[1]:.1f} s.")
    print(f"Time WITH cached results on model: {elapsed_times[0]:.1f} s.")
    print(hmodel.log())


def model_3():
    """Run model 3"""
    print(f"\n***MODEL 3***")
    hmodel = get_model("model3.yml")
    query = ["cars[:].price"]  # price for all cars
    response = hmodel.get(query, use_multi_processing=use_multi_processing)
    print(f"{response}")
    print(hmodel.log())


def model_2_component_cache():
    """Run model 2 and illustrate model-level caching"""
    print(f"\n***MODEL 2***")
    hmodel = get_model("model2.yml")
    query = [
        "cars[:].parts[:].price",  # price for all components for all cars
        "cars[:].price",  # price for all cars
    ]

    component_caching_levels = (False, True)
    for component_caching in component_caching_levels:
        hmodel.set_component_caching(component_caching)
        r = hmodel.get(query, use_multi_processing=use_multi_processing)
    pprint(r)

    elapsed_times = reversed(hmodel.log().get_all("elapsed_time"))
    for elapsed_time, component_caching in zip(elapsed_times, component_caching_levels):
        print(f"Component caching is {component_caching}: {elapsed_time:.1f} s.")

    print(hmodel.log())


use_multi_processing = False
model_0()
model_1()
model_2()
model_3()
model_2_component_cache()
