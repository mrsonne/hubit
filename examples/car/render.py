from .shared import get_model

hmodel1 = get_model("model1.yml", model_id=1)
queries = ['cars[0].price']


hmodel2 = get_model("model2.yml", model_id=2)
queries = ['cars[0].price']

hmodel1.render()
hmodel1.render(queries=queries)

hmodel2.render()
hmodel2.render(queries=queries)