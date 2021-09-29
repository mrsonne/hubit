{% include 'docs/shared/header.html' %}

# Examples

## Full examples in the repository
In the examples all calculation are, for simplicity, carried out directly in the 
`Hubit` component, but the component could just as well wrap a C library, request 
data from a web server or use an installed Python package. The examples are summarized below.

* [`examples/car`](https://github.com/mrsonne/hubit/tree/master/examples/car). This example encompass the four similar car models. The examples illustrate how the `Hubit` model file can be used to interface with cars models that carry out the same task, but have quite different levels of modularity. Further, the use of model-level caching and component-level caching is illustrated.
* [`examples/wall`](https://github.com/mrsonne/hubit/tree/master/examples/wall). This example illustrates heat flow calculations and cost calculations for a wall with two segments. Each wall segment has multiple wall layers that consist of different materials. The example demonstrates model rendering (`run_render.py`), simple queries (`run_queries.py`) with model level caching, reusing previously calculated results `run_precompute.py`, setting results manually (`run_set_results.py`) and input parameter sweeps (`run_sweep.py`). Most of the wall examples run with or without multi-processing.

To run, for example, the car example clone the repository and execute the command below from the project root 

```sh
python -m examples.car.run
```

## Car calculation

This tutorial follows, to a large extent, the example in [`examples/car`](https://github.com/mrsonne/hubit/tree/master/examples/car). The example will be explained and some key `Hubit` terminology will be introduced. 

In the example let us imagine that we are calculating the price of a car using based on the names of the parts. So the calculation involves a lookup of the price for each part and a summation of the parts prices.

### Components
First, your existing tools each need to be wrapped as a `Hubit` _component_. A `hubit` component is a computational task that has bindings to the input data and to the results data. The bindings define which attributes the component

- _consumes_ from the shared input data structure, 
- _consumes_ from the shared results data structure, and 
- _provides_ to the shared results data structure. 

From the bindings `Hubit` can check that all required input data and results data is available before the computational task is executed. The bindings are defined in a _model file_. 

### Component entrypoint
Below you can see some pseudo code for the calculation for the car price calculation. The example is available in [`mod1_cmp1.py`](https://github.com/mrsonne/hubit/tree/master/examples/car/components/mod1_cmp1.py)

```python
def price(_input_consumed, results_provided):
    # Extract required input data here
    counts = _input_consumed['part_counts'] 
    names = _input_consumed['part_names'] 

    # Look up the price of the part based on the part name (local data, database)
    unit_prices = [my_lookup(name) for name in names]

    # Compute results here (web service, C, Python ...)
    result = sum( [ count*unit_price 
                    for count, unit_price in zip(counts, unit_prices) ] )

    results_provided['car_price'] = result
```

The entrypoint function in a component (`price` in the example above) should expect the arguments `_input_consumed` and `results_provided` in that order. Results data calculated in the components should only be added to the latter. The values stored in the keys `part_counts` and `part_names` in `_input_consumed` are controlled by the bindings in the model file. 

### Model file & component bindings
Before we look at the bindings let us look at the input data. The input can, like in the example below, be defined in a yml file. In the car example the input data is a list containing two cars each with a number of parts

```yaml
cars:
  - parts: 
    - count: 4
      name: wheel1
    - count: 1
      name: chassis1
    - count: 2
      name: bumper
    - count: 1
      name: engine1
    - count: 1
      name: radio
  - parts: 
    - count: 4
      name: wheel2
    - count: 1
      name: chassis2
    - count: 2
      name: bumper
    - count: 1
      name: engine14
```

The `price` entrypoint above expects a list of part names be stored in the key `part_names` and a list of the corresponding part counts be stored in the key `part_counts`. Make such lists available in the expected fields, the model file should contain the lines below.

```yaml
consumes_input:
  - name: part_names # key in component input dict
    path: cars[IDX_CAR].parts[:@IDX_PART].name # path in input data
  - name: part_counts
    path: cars[IDX_CAR].parts[:@IDX_PART].count
```

The strings in square braces are called _index specifiers_. The index specifier `:@IDX_PART` refers to all items for the _index identifier_ `IDX_PART`. In this case the specifier contains a slice and a reference to an index identifier. The index specifier `IDX_CAR` is simply an index identifier and refers to a specific car. 

With the input data and bindings shown above, the content of `_input_consumed` in the `price` function for the car at index 1 will be 

```python
{'part_counts': [4, 1, 2, 1], 'part_names':  ['wheel2', 'chassis2', 'bumper', 'engine14']}
```

i.e. the components will have all counts and part names for a single car in this case the car at index 1 in the input. 

In the last line of the `price` function, the car price is added to the results

```python
results_provided['car_price'] = result
```

To enable the transfer of the calculated car price to the shared results data object we must add a binding from the internal component name `car_price` to an appropriate field in the shared results object. If, for example, we want to store the car price in a field called `price` at the same car index as where the input data was taken from, the binding below should be added to the model file.

```yaml
provides_results: 
  - name: car_price # internal name in the component
    path: cars[IDX_CAR].price # path in the shared results data
```

It is the index specifier `IDX_CAR` in the binding path that tells `Hubit` to store the car price at the same car index as where the input was taken from. Note that the component itself is unaware of which car (car index) the input represents. 

Collecting the bindings we get

```yaml
provides_results: 
  - name: car_price # internal name in the component
    path: cars[IDX_CAR].price # path in the shared data 
consumes_input:
  - name: part_name
    path: cars[IDX_CAR].parts[:@IDX_PART].name
  - name: part_counts
    path: cars[IDX_CAR].parts[:@IDX_PART].count
```

Read more about paths, index specifiers and index identifiers 
in the documentation for [`HubitModelPath`][hubit.config.HubitModelPath].

### Refactoring

The flexibility in the `Hubit` binding paths allows you to match the interfaces of your existing tools. Further, this flexibility enables you to refactor to get good modularity and optimize for speed when multi-processing is used. Below we will show three versions of the car model and outline some key differences when multi-processing is used.

#### Car model 0 
In car model 0 the price calculation receives an entire car object at a specific car index (`IDX_CAR`). This allows the component to store results data on the corresponding car index in the results data object that `Hubit` creates. 

```yaml
provides_results: 
  - name: car_price
    path: cars[IDX_CAR].price
consumes_input:
  - name: car
    path: cars[IDX_CAR]
```

This model allows quires such as `cars[:].price` and `cars[1].price`. If car objects in the input data only contains `count` and `name` (like in the example above) this simple model definition is more or less equivalent to the more elaborate model shown above. If, on the other hand, car objects in the input data contains more data that is not relevant for price calculation model 0 would expose that data to the price calculation. Further, in the implementation of the car prices calculation an undesirable tight coupling to the input data structure would be unavoidable. The entrypoint function could look something like this

```python
  counts, names = list(
      zip(
          *[(part["count"], part["name"]) for part in _input_consumed["car"]["parts"]]
      )
  )
  unit_prices = [my_lookup_function(name) for name in names]
  result = sum([count * unit_price for count, unit_price in zip(counts, unit_prices)])
  results_provided["car_price"] = result
```

Notice how the `parts` list and the `count` and `name` attributes are accessed directly on the car object leading to a tight coupling.

#### Car model 1
Model 1 is the one described above where the car price is calculated in a single component i.e. in a single worker process. Such an approach works well if the lookup of parts prices is fast and the car price calculation is also fast. If, however, the lookup is fast while the car price calculation is slow, and we imagine that another component is also consuming the parts prices, then the car price calculation would be a bottleneck. In such cases, separating the lookup from the price calculation would probably boost performance. Models 2 and 3 present two different ways of implementing such a separation.

#### Car model 2
In this version of the model the parts price lookup and the car price calculation are implemented in two separate components. Further, the component that is responsible for the price lookup retrieves the price for one part only. In other words, each lookup will happen in a separate asynchronous worker process. When all the lookup processes are done, the price component sums the parts prices to get the total car price. The relevant sections of the model file could look like this

```yaml
# price for one part
- consumes_input:
    - name: part_name
      path: cars[IDX_CAR].parts[IDX_PART].name 
    - name: part_count
      path: cars[IDX_CAR].parts[IDX_PART].count
  provides_results:
    - name: part_price
      path: cars[IDX_CAR].parts[IDX_PART].price

# car price from parts prices
- consumes_results:
    - name: prices
      path: cars[IDX_CAR].parts[:@IDX_PART].price
  provides_results: 
    - name: car_price 
      path: cars[IDX_CAR].price
```

Notice that the first component consumes a specific part index (`IDX_PART`) for a specific car index (`IDX_CAR`). This allows the component to store results data on a specific part index for a specific car index. The entrypoint function for the first component (price for one part) could look something like this

```python
def part_price(_input_consumed, results_provided):
    count = _input_consumed['part_count'] 
    name = _input_consumed['part_name'] 
    results_provided['part_price'] = count*my_lookup_function(name)
```

The entrypoint function for the second component (car price) could look like this

```python
def car_price(_input_consumed, results_provided):
    results_provided['car_price'] = sum( _input_consumed['prices'] )
```

In this refactored model `Hubit` will, when submitting a query for the car price using the multi-processor flag, execute each part price calculation in a separate asynchronous worker process. If the part price lookup is fast, the overhead introduced by multi-processing may be render model 2 less attractive. In such cases performing all the lookups in a single component, but still keeping the lookup separate from the car price calculation, could be a good solution. 

#### Car model 3
In this version of the car model all price lookups take place in one single component and the car price calculation takes place in another component. For the lookup component, the relevant sections of the model file could look like this

```yaml
# price for all parts
consumes_input:
  - name: parts_name
    path: cars[IDX_CAR].parts[:@IDX_PART].name 
  - name: parts_count
    path: cars[IDX_CAR].parts[:@IDX_PART].count
provides_results:
  - name: parts_price
    path: cars[IDX_CAR].parts[:@IDX_PART].price
```

Notice that the component consumes all part indices (`:@IDX_PART`) for a specific car index (`IDX_CAR`). This allows the component to store results data on all part indices for a specific car index. The entrypoint for the first component (price for all parts) could look something like this

```python
def part_price(_input_consumed, results_provided):
    counts = _input_consumed['parts_count'] 
    names = _input_consumed['parts_name'] 
    results_provided['parts_price'] = [count*my_lookup_function(name)
      for count, name in zip(counts, names)
    ]
```

In this model, the car price component is identical to the one used in model 2 and is therefore omitted here.

### Paths
To tie together the bindings with the the Python code that does the actual work you need to add the path of the Python source code file to the model file. For the first car model it could look like this.

```yaml
components:
  - path: ./components/price1.py 
    func_name: price
    provides_results: 
      - name: car_price
        path: cars[IDX_CAR].price
    consumes_input:
      - name: part_names
        path: cars[IDX_CAR].parts[:@IDX_PART].name
      - name: part_counts
        path: cars[IDX_CAR].parts[:@IDX_PART].count
```

The specified path should be relative to [`model's`][hubit.model.HubitModel] `base_path` attribute, which defaults to the location of the model file when the model is initialized using the [`from_file`][hubit.model.HubitModel.from_file] method. You can also use a [dotted path][hubit.config.HubitModelComponent] e.g.

```yaml
path: hubit_components.price1
is_dotted_path: True
```

where `hubit_components` would typically be a package you have installed in site-packages.

### Running
To get results from a model requires you to submit a _query_, which is a sequence of [`query paths`][hubit.config.HubitQueryPath] each referencing a field in the results data structure that you want to have calculated. After `Hubit` has processed the query, i.e. executed relevant components, the values of the queried attributes are returned in the _response_. A query may spawn many component workers that may be instance of the same or different model components. Below are two examples of queries and the corresponding responses.

```python
# Load model from file
hmodel = HubitModel.from_file('model1.yml', name='car')

# Load the input
with open(os.path.join(THISPATH, "input.yml"), "r") as stream:
    input_data = yaml.load(stream, Loader=yaml.FullLoader)

# Set the input on the model object
hmodel.set_input(input_data)

# Query the model
query = ['cars[0].price']
response = hmodel.get(query)
```

The response looks like this

```python
{'cars[0].price': 4280.0}
```

Is this case the parts prices will also be calculated by `Hubit` to create the response. A query for parts prices for all cars looks like this

```python
query = ['cars[:].parts[:].price']
response = hmodel.get(query)
```

and the corresponding response is

```python
{'cars[:].parts[:].price': [[480.0, 1234.0, 178.0, 2343.0, 45.0],
                            [312.0, 1120.0, 178.0, 3400.0]],
```

### Rendering
If Graphviz is installed `Hubit` can render models and queries. In the example below we have rendered the query `[cars[0].price]` i.e. the price of the car at index 0.


<a target="_blank" rel="noopener noreferrer" href="https://github.com/mrsonne/hubit/blob/master/examples/car/images/query_car_2.png">
  <img src="https://github.com/mrsonne/hubit/raw/master/examples/car/images/query_car_2.png" width="1000" style="max-width:100%;">
</a>

The graph illustrates nodes in the input data structure, nodes in the the results data structure, the calculation components involved in creating the response as well as hints at which attributes flow in and out of these components. The triple bar icon ≡ indicates that the node is accessed by index and should therefore be a list. The graph was created using the command below. 

```python
query = ['cars[0].price']
hmodel.render(query)
```

### Validation

Running

```python
hmodel.validate()
```
will validate various aspects of the model.

Running

```python
hmodel.validate(['cars[0].price'])
```
will validate various aspects of the query.

### Caching

#### Model-level caching. 
By default `Hubit` never caches results internally. A `Hubit` model can, however, write results to disk automatically by using the [`set_model_caching`][hubit.model.HubitModel.set_model_caching] method to set the caching level. Results caching is useful when you want to avoid spending time calculating the same results multiple times or to have `Hubit` create restart snapshots. The table below comes from printing the log after running model 2 with and without model-level caching

```python
print(hmodel.log())
```
```
--------------------------------------------------------------------------------------------------
Query finish time    Query took (s)        Worker name        Workers spawned Component cache hits
--------------------------------------------------------------------------------------------------
21-Mar-2021 20:46:31     0.1              car_price                0                 0
                                         part_price                0                 0
21-Mar-2021 20:46:31     1.8              car_price                3                 0
                                         part_price               14                 0
--------------------------------------------------------------------------------------------------
```

The second run (top) using the cache is much faster than the first run (bottom) that spawns 17 workers to complete the query. 

The model cache can be cleared using the [`clear_cache`][hubit.model.HubitModel.clear_cache]  method on a `Hubit` model. To check if a model has an associated cached result use [`has_cached_results`][hubit.model.HubitModel.has_cached_results] method on a `Hubit` model. Cached results for all models can be cleared by using [`hubit.clear_hubit_cache`][hubit.__init__.clear_hubit_cache].

#### Component-level caching 
Component-level caching can be activated using [set_component_caching][hubit.model.HubitModel.set_component_caching]. By default component-level caching is off. If component-level caching is on, the consumed data for all spawned component workers and the corresponding results will be stored in memory during execution of a query. If `Hubit` finds that, in the same query, two workers refer to the same model component and the input data are identical, the second worker will simply use the results produced by the first worker. The cache is not shared between sequential queries to a model. Also, the component-level cache is not shared between the individual sampling runs using ['get_many'][hubit.model.HubitModel.get_many].

The table below comes from printing the log after running car model 2 with and without component-level caching

```python
print(hmodel.log())
```
```
--------------------------------------------------------------------------------------------------
Query finish time    Query took (s)        Worker name        Workers spawned Component cache hits
--------------------------------------------------------------------------------------------------
21-Mar-2021 20:48:26     1.1              car_price                3                 2
                                         part_price               14                 6
21-Mar-2021 20:48:25     1.8              car_price                3                 0
                                         part_price               14                 0
--------------------------------------------------------------------------------------------------
```

The second run (top) uses component-caching and is faster than the first run (bottom). Both queries spawn 17 workers in order to complete the query, but in the case where component-caching is active (top) 8 workers reuse results provided by the remaining 9 workers. 

For smaller jobs any speed-up obtained my using component-level caching cannot be seen on the wall clock when using multi-processing. The effect will, however, be apparent in the model [log][hubit.model.HubitModel.log] as seen above.
