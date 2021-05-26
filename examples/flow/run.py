from pprint import pprint
from .shared import get_model

# logging.basicConfig(level=logging.INFO)
# For hard refs
hmodel = get_model("model1.yml")
# query = ["tanks[0].vol_outlet_flow"]
# query = ["tanks[1].vol_outlet_flow"]
query = ["tanks[2].vol_outlet_flow"]
# query = [
#     "tanks[0].vol_outlet_flow",
#     "tanks[1].vol_outlet_flow",
#     "tanks[2].vol_outlet_flow",
# ]

# Fatal error. Multiple providers for query 'tanks[:].vol_outlet_flow': ['cmp0@./components/mod1.main', 'cmp1@./components/mod1.main']
# query = ["tanks[:].vol_outlet_flow"]
response = hmodel.get(query, use_multi_processing=False)
print(response)
