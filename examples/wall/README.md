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
The wall material and dimensions can be found in `input.yml`. Note that the 
number of layers in the two segments differ which highlight `hubit`s capability 
to handle non-rectangular data models.

## Model
The wall model is defined in `model.yml` and contain calculation components 
that may service e.g. engineering and management. In general using different 
queries it is straight forward to set up different reports for different stakeholder 
be it management, internal design engineers, clients or independant verification agencies.

### Components
The source code for all components can be found in the `components` folder. The 
components can, in this example, schematically be divided into engineering 
components and management components.

#### Engineering components

1. Segment-layer thermal conductivities (`components/thermal_conductivity.py`).
2. Segment thermal profiles and heat flux (`components/thermal_profile.py`).
3. Segment heat flow (`components/heat_flow.py`).
4. Segment-layer volumes (`MAKE ME`).
5. Segment-layer weights (`MAKE ME`).
6. Maximum heat flow (`MAKE ME`).

The heat flow (3) could be calculated in the thermal profile (2) but here
it is kept as a separate component to increase modularity and to maximize the speed-up 
obtained by multi-processing.

#### Management components

* Segment costs (`MAKE ME`).
* Total cost (`MAKE ME`).

In the example a time delay has been added to the component to simulate 
heavier computational load or a latency in a web service.

## Example calculations
The purpose of the examples are summarized below. A more thorough description 
can be found in the documentation in the individual files.

* `run_queries.py` show examples of some queries.
* `run_precompute.py` shows how results from a query can be reused in a subsequent query. 
* `run_set_results.py` shows how to manually set results on the model to bypass a model component.
* `run_sweep.py` shows how to perform a sweep over input values.

To run an example run the script from the project root for example  
`python3 -m examples.wall.run_queries`

