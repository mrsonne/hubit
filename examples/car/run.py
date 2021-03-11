import time
from pprint import pprint
import logging
from .shared import get_model
from hubit import clear_hubit_cache

# logging.basicConfig(level=logging.INFO)


def model_1():
    """Run model 1 and illustrate worker-level caching

    input.yml shows that cars[0] and cars[2] are identical so the effect
    of worker caching on the execution time can be seen. The execution time
    with worker caching is expected to be ~2/3 of the execution time without
    worker chaching (the calculation for one car can be reused).
    """
    print(f"\n***MODEL 1***")

    hmodel1 = get_model("model1.yml")
    query = ["cars[0].price", "cars[1].price", "cars[2].price"]

    # With worker caching
    time1 = time.time()
    hmodel1.set_worker_caching(True)
    response = hmodel1.get(query, use_multi_processing=False)

    # Without worker caching
    time2 = time.time()
    hmodel1.set_worker_caching(False)
    response = hmodel1.get(query, use_multi_processing=False)
    time3 = time.time()

    print(response)
    print(f"Time WITH worker caching: {time2 - time1:.1f} s. ")
    print(f"Time WITHOUT worker caching: {time3 - time2:.1f} s. ")


def model_2():
    """Run model 2 and illustrate model-level caching"""
    print(f"\n***MODEL 2***")
    model_caching_mode = "after_execution"
    # model_caching_mode = "incremental"
    # model_caching_mode = "never"
    use_results = "cached"
    # use_results = "none"

    clear_hubit_cache()
    hmodel2 = get_model("model2.yml")
    hmodel2.set_model_caching(model_caching_mode)
    query = [
        "cars[:].parts[:].price",  # price for all components for all cars
        "cars[:].price",  # price for all cars
    ]
    time1 = time.time()
    response = hmodel2.get(query, use_results="cached")
    time2 = time.time()
    response = hmodel2.get(query, use_results="cached")
    time3 = time.time()
    pprint(response)
    print(f"\nTime WITHOUT cached results on model: {time2 - time1:.1f} s.")
    print(f"Time WITH cached results on model: {time3 - time2:.1f} s.")


def model_3():
    """Run model 3"""
    print(f"\n***MODEL 3***")
    hmodel3 = get_model("model3.yml")
    query = ["cars[:].price"]  # price for all cars
    response = hmodel3.get(query)
    print(f"{response}")


model_1()
model_2()
model_3()
