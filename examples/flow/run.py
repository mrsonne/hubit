from pprint import pprint
from .shared import get_model

# logging.basicConfig(level=logging.INFO)
# For hard refs
hmodel = get_model("model1.yml")

query = ["lines[0].tanks[0].vol_outlet_flow"]
print(f"\nSpawns 1 worker: {query}")
response = hmodel.get(query, use_multi_processing=False)
print("response", response)
print(hmodel.log())
hmodel.clean_log()

query = ["lines[0].tanks[1].vol_outlet_flow"]
print(f"\nSpawns 2 workers: {query}")
response = hmodel.get(query, use_multi_processing=False)
print("response", response)
print(hmodel.log())
hmodel.clean_log()

query = ["lines[0].tanks[2].vol_outlet_flow"]
print(f"\nSpawns 3 workers: {query}")
response = hmodel.get(query, use_multi_processing=False)
print("response", response)
print(hmodel.log())
hmodel.clean_log()

query = [
    "lines[0].tanks[0].vol_outlet_flow",
    "lines[0].tanks[1].vol_outlet_flow",
    "lines[0].tanks[2].vol_outlet_flow",
]
print(f"\nSpawns 3 workers: {query}")
response = hmodel.get(query, use_multi_processing=False)
print("response", response)
print(hmodel.log())
hmodel.clean_log()

query = ["lines[0].tanks[:].vol_outlet_flow"]
print(f"\nSpawns 3 workers: {query}")
response = hmodel.get(query, use_multi_processing=False)
print("response", response)
print(hmodel.log())


# query = ["lines[:].tanks[:].vol_outlet_flow"]
# print(f"\nSpawns 3 workers: {query}")
# response = hmodel.get(query, use_multi_processing=False)
# print("response", response)
# print(hmodel.log())
