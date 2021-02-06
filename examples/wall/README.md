# Calculations for a wall

```
     __________
    |          |
    |          |
    |__________|
    |__________|
    
```

Both engineering and management. Same model results provided controlled by query.

Using different queries it is therefore straight forward to set up different reports 
for management, for clients, for independant verification agencies, and 
for internal design engineers.

## Input and model

## Components
The source code for all components can be found in the `components` folder. The 
components can be divided into engineering models and management model.

### Engineering models

* Segment-layer thermal conductivities
* Segment thermal profiles
* Segment-layer volumes
* Segment-layer weights
* Maximum heat flow

### Management models

* Segment costs
* Total cost

## Example calculations

The pupose of the examples are summarized below. A more thorough description 
can be found in the documentation in the individual files.

* `run_queries.py` contains
* `run_precompute.py`
* `run_set_results.py`
* `run_sweep.py`

From the project root run for example 
`python3 -m examples.wall.run_queries`

