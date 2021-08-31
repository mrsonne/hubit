from pprint import pprint
from .shared import get_model

# logging.basicConfig(level=logging.INFO)
# For hard refs
hmodel = get_model("model1.yml")

# Should result in a number
query = ["sites[0].lines[0].tanks[0].vol_outlet_flow"]
print(f"\nQuery")
pprint(query)
print(f"Spawns 1 worker")
response = hmodel.get(query, use_multi_processing=False)
print("Response (one path & value):")
pprint(response)
print(hmodel.log())
hmodel.clean_log()

# Should result in a number
query = ["sites[0].lines[0].tanks[1].vol_outlet_flow"]
print(f"\nQuery")
pprint(query)
print(f"Spawns 2 workers")
response = hmodel.get(query, use_multi_processing=False)
print("Response (one path & value):")
pprint(response)
print(hmodel.log())
hmodel.clean_log()

# Should result in a number
print(f"\nQuery")
query = ["sites[0].lines[0].tanks[2].vol_outlet_flow"]
pprint(query)
print(f"Spawns 3 workers")
response = hmodel.get(query, use_multi_processing=False)
print("Response (one path & value):")
pprint(response)
print(hmodel.log())
hmodel.clean_log()

# # Should result in three numbers
query = [
    "sites[0].lines[0].tanks[0].vol_outlet_flow",
    "sites[0].lines[0].tanks[1].vol_outlet_flow",
    "sites[0].lines[0].tanks[2].vol_outlet_flow",
]
print(f"\nQuery")
pprint(query)
print(f"Spawns 3 workers")
response = hmodel.get(query, use_multi_processing=False)
print("Response (three paths & corresponding values)")
pprint(response)
print(hmodel.log())
hmodel.clean_log()

# Should result in 1D array
query = ["sites[0].lines[0].tanks[:].vol_outlet_flow"]
print(f"\nSpawns 3 workers: {query}")
response = hmodel.get(query, use_multi_processing=False)
print("Response (One path with list as value):")
print(response)
print(hmodel.log())
hmodel.clean_log()

# Should result in double nested list
query = ["sites[0].lines[:].tanks[:].vol_outlet_flow"]
print(f"\nSpawns 3 workers: {query}")
response = hmodel.get(query, use_multi_processing=False)
print("Response (One path with double nested list as value):")
print(response)
print(hmodel.log())
hmodel.clean_log()


# Should result in triple nested list
query = ["sites[:].lines[:].tanks[:].vol_outlet_flow"]
print(f"\nSpawns 3 workers: {query}")
response = hmodel.get(query, use_multi_processing=False)
print("Response (One path with triple nested list as value):")
print(response)
print(hmodel.log())
hmodel.clean_log()
