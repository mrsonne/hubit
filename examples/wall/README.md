# Heat flow through a wall

In this example we consider a wall that consists of three segments as shown in the illustration below.

```
Face view wall (not to scale)
     _______________
    |   segment 1   | 1.5 m
    |_______________|
    |               | 
    |   segment 2   | 2.0 m
    |_______________|
    |               | 
    |   segment 3   | 2.0 m
    |_______________|
           3.0 m
```

Each wall segment consists of different layers as shown in the side view below.

```
Side view of the wall (not to scale)

                      brick air  rockwool 
                        |    |   |     brick
                        |    |   |     |
            Inside      v    v   v     v    Outside
                     ----------------------
                     |      | |    |      | segment 1 (wall: brick-air-rockwool-brick)
temperature = 320 K  |      | |    |      | temperature = 273 K   
                     ----------------------        
                                      || ||      
                                      || || segment 2 (window: glass-air-glass)
temperature = 300 K                   || || temperature = 273 K
                     ----------------------
                     |         | |        |      
                     |         | |        | segment 3 (wall: concrete-EPS-concrete)
temperature = 300 K  |         | |        | temperature = 273 K
                     ----------------------
                        ^       ^     ^ 
                        |       |     |
                     concrete   |     concrete 
                               EPS 
```

The wall materials, dimensions and other input can be found in wall input file [`examples/wall/input.yml`](https://github.com/mrsonne/hubit/blob/master/examples/wall/input.yml). Note that the number of wall layers in the two segments differ, which illustrates that `Hubit` can handle non-rectangular data.

## Model

The wall model is defined in [`examples/wall/model.yml`](https://github.com/mrsonne/hubit/blob/master/examples/wall/model.yml) and define bindings between calculation components that provides certain results. The components are explained in greater detail later. With the model in place `Hubit` allows users to query the results data structure. For example, to get the "total_cost" and "total_heat_loss" for the wall we would write

```python
from hubit.model import HubitModel
hmodel = HubitModel.from_file('model.yml', name='wall')
query = ["total_cost", "heat_transfer_number"]
response = hmodel.get(query)
```

The response to the query is

```python
{
  'total_cost': 2365.600380096421, 
  'heat_transfer_number': 0.8888377547279751
}
```

Behind the scenes `Hubit` constructs and executes the call graph for the query. Only components that provide results that are necessary for constructing the response are spawned. Therefore, the query `segment[0].cost` would only spawn calculations required to calculate the cost of wall segment 0 while the query `total_cost` invokes cost calculations for all segments. To understand more about this behavior read the [Call graph & multi-processing](#call-graph-multi-processing) section below.

By using different queries it is straight forward to set up reports for different audiences, each with a customized content, but based on the same model and the same input. Such different reports can service different stakeholders e.g. management, internal design engineers, clients or independent verification agencies.

### Components

The source code for the wall model components can be found in the [`examples/wall/components`](https://github.com/mrsonne/hubit/tree/master/examples/wall) folder in the repository and are referenced from [`the model configuration file`](https://github.com/mrsonne/hubit/tree/master/examples/wall/model.yml). A time delay has been added in some of the components to simulate a heavy computational load or a latency in a web service. The time delay illustrates the asynchronous capabilities in `Hubit`.

Some of the calculation components deals with the physics part of the wall model. These components include

1. [`thermal_conductivity.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/components/thermal_conductivity.py). Simple lookup of thermal conductivities based on the material name.
2. [`thermal_profile.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/components/thermal_profile.py). A calculation of the temperature for all wall layers in a segment as well
as the heat flux in the segment. We assume one-dimensional heat flow, and thus each segment can be treated independently.
3. [`heat_flow.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/components/heat_flow.py). Calculates the heat flow through a segment.
4. [`heat_transfer_number.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/components/heat_transfer_number.py). Calculates the overall heat transfer number and wall energy classification. The wall energy classification ranges from A to D where A indicates the most insulating wall (best) and D indicates the least insulating wall (worst).

Many (all) of the components could have been joined in a single component, but here they are kept as  separate components to increase modularity, to assure that any query only spawns a minimum of calculations and to maximize the potential speed-up obtained by multi-processing.

The wall cost is calculated by the two components below

5. [`segment_cost.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/components/segment_cost.py). Calculates wall segment cost. In the code notice how segments with type 'window' are handled differently compared to other segments types.
6. [`total_cost.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/components/total_cost.py). Calculates wall total cost.

To support the cost calculations two extra engineering components are included

7. [`volume.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/components/volume.py). Calculates the volume of wall layers.
8. [`weight.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/components/weight.py). Calculates the weight of wall layers.

### Call graph & multi-processing

`Hubit` is event-driven and components are spawned dynamically. The bindings that are used to set up the relations between components are defined in `model.yml`

To illustrate the cascade of events that spawn the necessary calculations let us consider a query for the wall `total_cost`. In the model file the total cost is _provided_ by `total_cost.py`.

```yml
path: ./components/total_cost.py
func_name: total_wall_cost
provides_results:
  - name: cost
    path: total_cost
consumes_results:
  - name: segment_costs
    path: segments[:@IDX_SEG].cost
```

Further, the model file reveals that the `total_cost.py` _consumes_ the costs for all segments (`segments[:@IDX_SEG].cost`). The segment costs are, in turn, provided by `segment_cost.py` as seen from the component definition below, which is also taken from `model.yml`.

```yml
path: ./components/segment_cost.py
func_name: cost
provides_results:
  - name: cost
    path: segments[IDX_SEG].cost
consumes_input: 
  - name: materials
    path: segments[IDX_SEG].layers[:@IDX_LAY].material
  - name: type
    path: segments[IDX_SEG].type
consumes_results: 
  - name: weights
    path: segments[IDX_SEG].layers[:@IDX_LAY].weight
```

Since the segment costs are not in the results data to begin with `Hubit` spawns the `segment_cost.py` calculation. To calculate the segment cost, the material and segment weight must be known for each layer in the segment since these attributes are specified in the `consumes_results` section. The segment cost component expects the layer materials and weights to be available at `segments[IDX_SEG].layers[:@IDX_LAY].material` and `segments[IDX_SEG].layers[:@IDX_LAY].weight`,  respectively.

The weights are calculated in `weight.py` and the material (part of the input) is used to look up a price in `segment_cost.py`. Inspecting `model.yml` shows that the weight component _consumes_ the layer volume calculated in `volume.py`. So the original query triggers a cascade of new auxiliary queries that each may spawn new calculations. The calculations are put on hold until the all required data is available. Once this data becomes available the calculation starts and may, after completion, provide data that trigger other pending calculations. Since the cost and heat transfer calculations for each wall segment are independent the event-driven architecture allows `Hubit` to execute these calculations for each wall segment in parallel if the multi-processing flag is set to `True`.

As we have previously seen, the response to the `'heat_transfer_number'` query is

```python
{'heat_transfer_number': 0.8888377547279751}
```

All the results that were used to process the query can be accessed using `hmodel.results`

```python
{'energy_class': 'C',
 'heat_transfer_number': 0.8888377547279751,
 'segments': {0: {'heat_flux': 13.134093452714046,
                  'heat_transfer_number': 0.2794487968662563,
                  'layers': {0: {'k_therm': 0.47,
                                 'outer_temperature': 317.20551203133743},
                             1: {'k_therm': 0.025,
                                 'outer_temperature': 306.6982372691662},
                             2: {'k_therm': 0.034,
                                 'outer_temperature': 275.79448796866257},
                             3: {'k_therm': 0.47, 'outer_temperature': 273.0}}},
              1: {'heat_flux': 33.540372670807464,
                  'heat_transfer_number': 1.2422360248447208,
                  'layers': {0: {'k_therm': 0.8,
                                 'outer_temperature': 299.91614906832297},
                             1: {'k_therm': 0.025,
                                 'outer_temperature': 273.083850931677},
                             2: {'k_therm': 0.8,
                                 'outer_temperature': 272.99999999999994}}},
              2: {'heat_flux': 26.79699248120301,
                  'heat_transfer_number': 0.9924812030075189,
                  'layers': {0: {'k_therm': 1.1,
                                 'outer_temperature': 296.34586466165416},
                             1: {'k_therm': 0.033,
                                 'outer_temperature': 276.0451127819549},
                             2: {'k_therm': 1.1, 'outer_temperature': 273.0}}}}}
```

## Example calculations

The purpose of the examples are summarized below. To run an example using the `hubit` source code run the example script from the project root e.g. `python3 -m examples.wall.run_queries`. In some of the examples you can toggle the multi-processing flag to see the performance difference with and without multi-processing. The performance change obtained by activating multi-processing depends on the time spent in the components. You can try to adjust the sleep time in `thermal_conductivity.py` and `thermal_profile.py`.

### Rending the model

To get a graphical overview of a `hubit` model the model can be rendered **if Graphviz is installed**. The rendition of the wall model is shown below  

<a target="_blank" rel="noopener noreferrer" href="https://github.com/mrsonne/hubit/blob/master/examples/wall/images/model_wall.png">
  <img src="https://github.com/mrsonne/hubit/raw/master/examples/wall/images/model_wall.png" width="1000" style="max-width:100%;">
</a>

`Hubit` can also render a query as illustrated below

<a target="_blank" rel="noopener noreferrer" href="https://github.com/mrsonne/hubit/blob/master/examples/wall/images/query_wall.png">
  <img src="https://github.com/mrsonne/hubit/raw/master/examples/wall/images/query_wall.png" width="1000" style="max-width:100%;">
</a>

Notice how the graph representing the query only includes a subset of all the model components. When a query is rendered only the relevant components for that particular query are shown. The example code can be found in
[`examples/wall/render.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/render.py)
.

### Queries

This example runs various queries. First the queries are submitted individually, which causes redundant calculations. Second, all the queries are submitted together in which case `Hubit` will assure that the same result is not calculate multiple times. An example is shown in [`examples/wall/run_queries.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/run_queries.py).

### Indexing from the back in the model

To illustrate the use of negative indices, the [model file](https://github.com/mrsonne/hubit/tree/master/examples/wall/model.yml) includes a component that calculates the minimum temperature between the outermost and second outermost wall layers. The temperature at this interface could be of particular engineering interest. To this end the `Hubit` model component subscribes to `segments[IDX_SEG].layers[-2@IDX_LAY].outer_temperature` and the minimum temperature is stored in the path `service_layer_minimum_temperature`.

The example in [`examples/wall/run_min_temperature.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/run_min_temperature.py) executes `hmodel.get(["service_layer_minimum_temperature"])` which gives the response `{'service_layer_minimum_temperature': 275.79}`. The `Hubit` log reveals that 10 thermal conductivity and 3 thermal profile workers were spawned to produce the response.

```
------------------------------------------------------------------------------------------------------------------------------
Query finish time    Query took (s)                      Worker name                       Workers spawned Component cache hits
-------------------------------------------------------------------------------------------------------------------------------
14-Mar-2022 13:06:16      2.5                  ./components/heat_flow.heat_flow                   0                 0
                                    ./components/heat_transfer_number.heat_transfer_number        0                 0
                                              ./components/min_temperature.main                   1                 0
                                                ./components/segment_cost.cost                    0                 0
                                    ./components/thermal_conductivity.thermal_conductivity       10                 0
                                          ./components/thermal_profile.thermal_prof               3                 0
                                           ./components/total_cost.total_wall_cost                0                 0
                                                  ./components/volume.volume                      0                 0
                                                  ./components/weight.weight                      0                 0
-------------------------------------------------------------------------------------------------------------------------------
```

### Re-using old results

After completing a query the `Hubit` model instance will store the results. If a new query is submitted using the same model and the `use_results` argument is set to `"current"` in  [`get`][hubit.model.HubitModel.get], `Hubit` will use the cached results instead of re-calculating them i.e. `Hubit` will bypass the components that provide the cached results. For example, if the layer costs are queried first followed by a query for the wall total cost, which consumes the layer cost, the layer cost will not be calculated in the second query. An example is shown in
[`examples/wall/run_precompute.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/run_precompute.py)

The results can be retrieved from [`results`][hubit.model.HubitModel.results] on the `Hubit` model instance and can then be saved to disk or otherwise persisted.

### Manually set results

Results can be manually set on the model using the [`set_results()`][hubit.model.HubitModel.set_results] method on a `Hubit` model instance. In subsequent queries `Hubit` will then omit re-calculating the results that have been set, thus bypassing the corresponding providers. The values that are manually set could represent some new measurements that you want to see the effect of when propagated in through the remaining components downstream of the component that is bypassed. The values could also represent persisted results that you want to augment with additional results or analyses without running the entire model again. An example is shown in [`examples/wall/run_set_results.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/run_set_results.py).

### Sweep input parameters

`Hubit` can sweep over different values of the input attributes. The example shows the energy class and cost for different value of the insulation thickness and for different values of the wall materials. [`examples/wall/run_sweep.py`](https://github.com/mrsonne/hubit/tree/master/examples/wall/run_sweep.py) shows an example sweep which results in the table below

```
Wall sweep
-------------------------------------------------------------------------------------------------------------------------
Inner Mat.   Outer Mat.   Seg0 Ins. Thck. [m]   Seg1 Ins. Thck. [m]   heat_transfer_number   energy_class   total_cost
-------------------------------------------------------------------------------------------------------------------------
brick        brick        0.08                  0.025                 0.80                   C              2761
brick        brick        0.12                  0.065                 0.65                   B              2804
brick        concrete     0.08                  0.025                 0.84                   C              1746
brick        concrete     0.12                  0.065                 0.66                   B              1789
concrete     brick        0.08                  0.025                 0.84                   C              1619
concrete     brick        0.12                  0.065                 0.66                   B              1662
concrete     concrete     0.08                  0.025                 0.89                   C              604
concrete     concrete     0.12                  0.065                 0.68                   B              647
-------------------------------------------------------------------------------------------------------------------------
```

The information in the table could conveniently be visualized in a parallel coordinates plot.
