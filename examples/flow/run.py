from pprint import pprint
from .shared import get_model

# logging.basicConfig(level=logging.INFO)
# For hard refs
hmodel = get_model("model1.yml")

# Spawns 1 worker
# query = ["tanks[0].vol_outlet_flow"]

# Spawns 2 workers
# query = ["tanks[1].vol_outlet_flow"]

# Spawns 3 workers
# query = ["tanks[2].vol_outlet_flow"]


# Spawns 3 workers
# query = [
#     "tanks[0].vol_outlet_flow",
#     "tanks[1].vol_outlet_flow",
#     "tanks[2].vol_outlet_flow",
# ]

# Spawns 3 workers
query = ["tanks[:].vol_outlet_flow"]

response = hmodel.get(query, use_multi_processing=False)

print(response)
print(hmodel.log())
