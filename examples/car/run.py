from pprint import pprint
from .shared import get_model

hmodel1 = get_model("model1.yml")
query = ["cars[0].price", "cars[1].price"]
response = hmodel1.get(query)
print(response)

hmodel2 = get_model("model2.yml")
queries = [
    "cars[:].parts[:].price",  # price for all components for all cars
    "cars[:].price",  # price for all cars
]
response = hmodel2.get(queries)
pprint(response)


hmodel3 = get_model("model3.yml")
queries = ["cars[:].price"]  # price for all cars
response = hmodel3.get(queries)
print(response)
