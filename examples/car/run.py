from pprint import pprint
from .shared import get_model
from hubit import clear_hubit_cache

clear_hubit_cache()

caching_mode = "incremental"
caching_mode = "after_execution"
# caching_mode = "never"
# use_results = "cached"
use_results = "none"

hmodel1 = get_model("model1.yml")
hmodel1.set_model_caching(caching_mode)
hmodel1.clear_cache()
query = ["cars[0].price", "cars[1].price", "cars[2].price"]
response = hmodel1.get(query, use_results=use_results)
print(response)

hmodel2 = get_model("model2.yml")
hmodel2.set_model_caching(caching_mode)
query = [
    "cars[:].parts[:].price",  # price for all components for all cars
    "cars[:].price",  # price for all cars
]
response = hmodel2.get(query, use_results=use_results)
pprint(response)


hmodel3 = get_model("model3.yml")
hmodel3.set_model_caching(caching_mode)
query = ["cars[:].price"]  # price for all cars
response = hmodel3.get(query, use_results=use_results)
print(response)
