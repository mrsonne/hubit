from pprint import pprint
from .shared import get_model

# use_results = "snapshot"
use_results = 'none'

hmodel1 = get_model("model1.yml")
query = ["cars[0].price", "cars[1].price"]
response = hmodel1.get(query, use_results=use_results)
print(response)

hmodel2 = get_model("model2.yml")
query = [
    "cars[:].parts[:].price",  # price for all components for all cars
    "cars[:].price",  # price for all cars
]
response = hmodel2.get(query, use_results=use_results)
pprint(response)


hmodel3 = get_model("model3.yml")
query = ["cars[:].price"]  # price for all cars
response = hmodel3.get(query, use_results=use_results)
print(response)
