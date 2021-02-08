import logging
from .utils import get_model, HubitModel

logging.basicConfig(level=logging.INFO)

def termal_query(hmodel: HubitModel, mpworkers: bool=False) -> None:
    """Demonstrates some query functionality into the thermal part of the
    wall composite model.

    Args:
        hmodel (HubitModel): Hubit model to be used
        render (bool, optional): Run query rendering. Defaults to True.
        mpworkers (bool, optional): Use multiprocessing. Defaults to False.
    """
    # Query validation fails for at
    # try:
    #     hmodel.validate(["segments.0.layers.0.doesnt_exist"])
    # except HubitModelQueryError as err:
    #     print(err)

    # Make the queries
    queries = (
                # ["segments[:].layers[:].weight"],
                ["heat_transfer_number", 'energy_class', 'total_cost'], 
                # ["segments[:].heat_flow"], 
                # ["segments[:].layers[:].outer_temperature"], 
                # ["segments[0].layers[0].outer_temperature"],   
                # ["segments[:].layers[1].k_therm"], 
                # ["segments[0].layers[0].k_therm"],
                # ["segments[0].layers[:].k_therm"], 
                # ["segments[:].layers[0].k_therm"],
                # ["segments[:].layers[:].k_therm"],
              ) 

    # Run queries one by one (slow)
    for query in queries:
        print(f'Query: {query}')
        response = hmodel.get(query,
                              mpworkers=mpworkers)
        print(response)
        print('')


    # Run queries as one (fast). The speed increase comes from Hubit's 
    # results caching that acknowleges that the first query actually produces 
    # the results for all the remaining queries 
    queries = [item for query in queries for item in query]
    response = hmodel.get(queries,
                          mpworkers=mpworkers)
    print(response)
    print('')


if __name__ == '__main__': # Main guard required on windows if mpworkers = True
    hmodel = get_model()
    use_multiprocessing = True
    termal_query(hmodel, mpworkers=use_multiprocessing)
