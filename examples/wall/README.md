# Calculations for a wall

In this example we consider a wall that consists of two segments 
as shown in the illustraton below. 

``` 
Wall face view (not to scale)
     ________________
    |   segment 1   | 1.5 m
    | ______________|
    |               | 
    |   segment 2   | 2.5 m
    |_______________|
           3.0 m
```

A side view of the wall is shown below.

```
Wall side view (not to scale)

     brick air  rockwool 
       |    |   |     brick
       |    |   |     |
       v    v   v     v
    ______________________
    |      | |    |      |
    |      | |    |      | segment 1
    ----------------------
    |         | |        |
    |         | |        | segment 2
    |         | |        |
    ----------------------
       ^       ^     ^ 
       |       |     |
    concrete   |     concrete 
               styrofoam 
```

The wall materials, dimensions and other input can be found in wall input file `input.yml`. 
Note that the number of wall layers in the two segments differ, which highlights `hubit`s capability 
to handle non-rectangular data models.

## Model
The wall composite model is defined in `model.yml` and define calculation components 
that provides cetain results. With the model in place `hubit` allows users to query the 
results data structure. For examples to get the "total_cost" and "total_heat_loss" 
would look like this

```python
from hubit import HubitModel
hmodel = HubitModel("model.yml")
query = ["total_cost", "total_heat_loss"]
response = hmodel.get(query)
```

Behind the scenes `hubit` construct and executes the call graph for the query. Only 
components that provide results that are necessary for constructing the 
response are spawned. Therefore, the query `segment[0].cost` would only spawn calculations
required to calculate the cost of wall segment 0 while the query `total_cost` envokes cost 
calculations for all segments. To understand more on this behavior read the 
"Components" section below.

By using different queries it is straight forward to set up various reports, each with 
a customized content, based on the same model and the same input i.e. with a single 
source of truth. Such different reports can service different 
stakeholders e.g. management, internal design engineers, clients or independant 
verification agencies.

### Components
The source code for all components can be found in the `components` folder. 
To facilitate the description, let us divide the components into two categories: 
engineering components and management components. These categories are somewhat 
arbitrary and are actually not needed in `hubit`.

#### Engineering components
These calculations encompass the physics part of the wall model.

1. `thermal_conductivity.py`. Simple lookup of thermal condutivities based on the material name.
2. `components/thermal_profile.py`. Calculation of the temperature of all wall layers in a segment as well as the heat flux. 
3. `components/heat_flow.py`. The heat flow through a segment.
4. `MAKE ME`. Calculate the total heat flow through the wall (all segments) and find the segment with the highest heat flow. 

The heat flow (3) could be calculated in the thermal profile (2), but here
it is kept as a separate component to increase modularity and to maximize the speed-up 
obtained by multi-processing.

To support the cost calculations (see below) two extra components are included

5. `MAKE ME`. Calculate the volume of wall layers. 
6. `MAKE ME`. Calculate the weight of wall layers.

#### Management components

* Segment costs (`MAKE ME`).
* Total cost (`MAKE ME`).

In the example a time delay has been added to the component to simulate 
heavier computational load or a latency in a web service.

Even driven. Cascade
 below and to see how the is defined in a 
`hubit` composite model please look at `model.yml`

## Example calculations
The purpose of the examples are summarized below. A more thorough description 
can be found in the documentation in the individual files.

* `run_queries.py` show examples of some queries.
* `run_precompute.py` shows how results from a query can be reused in a subsequent query. 
* `run_set_results.py` shows how to manually set results on the model to bypass a model component.
* `run_sweep.py` shows how to perform a sweep over input values.

To run an example run the script from the project root for example  
`python3 -m examples.wall.run_queries`

