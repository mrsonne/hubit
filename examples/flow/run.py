from pprint import pprint
from .shared import get_model

# logging.basicConfig(level=logging.INFO)
hmodel = get_model("model1.yml")
# query = ["inlets[:].tanks[2].inflow"]

# For hard refs
# query = ["inlets[0].tanks[2].inflow"]
query = ["inlets[1].tanks[2].inflow"]
# query = ["inlets[1].tanks[1].inflow"]

response = hmodel.get(query, use_multi_processing=False)
print(response)
