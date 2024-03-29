# The price of a car

In this example we consider a simplified price calculation for a car. The example some basic `hubit` features and shows three different ways of implementing the car prices calculation. To a large extent, the example follows [`examples/car`](https://github.com/mrsonne/hubit/tree/master/examples/car). The example will be explained and some key `Hubit` terminology will be introduced.

In the example let us imagine that we are calculating the price of a car based on the names of the individual parts. So the calculation involves a lookup of the price for each part and a summation of the parts prices.

## Components

First, your existing tools each need to be wrapped as a `Hubit` [component][hubit.config.HubitModelComponent]. A `Hubit` component is a computational task that has bindings to the input data and to the results data. The [bindings][hubit.config.HubitBinding] define which attributes the component

- _consumes_ from the shared input data structure,
- _consumes_ from the shared results data structure, and
- _provides_ to the shared results data structure.

From the bindings `Hubit` can check that all required input data and results data is available before the computational task is executed. The bindings are defined in a _model configuration file_ and are passed to the component _entrypoint function_.

### Component entrypoint function

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

The entrypoint function in a component (`price` in the example above) should expect the arguments `_input_consumed` and `results_provided` in that order. Results data calculated in the components should only be added to the latter. The values stored in the keys `part_counts` and `part_names` in `_input_consumed` are controlled by the bindings in the model configuration file.

### Component bindings

Before we look at the _bindings_ let us look at the input data. The input can, like in the example below, be defined in a yml file. In the car example the input data is a list containing two cars each with a number of parts

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

The `price` entrypoint function above expects a list of part names stored in the field `part_names` and a list of the corresponding part counts stored in the field `part_counts`. To make such lists available for the entrypoint function, the model configuration file should contain the lines below.

```yaml
consumes_input:
  - name: part_names # key in _input_consumed exposed to the entrypoint function
    path: cars[IDX_CAR].parts[:@IDX_PART].name # path in input data
  - name: part_counts
    path: cars[IDX_CAR].parts[:@IDX_PART].count
```

The strings in square braces are called [index specifiers][hubit.config.ModelIndexSpecifier]. The index specifier `:@IDX_PART` refers to all items for the _index identifier_ `IDX_PART`. The index specifier `IDX_CAR` is simply refers to a specific car. The index identifiers (here `IDX_PART` and `IDX_CAR`) are identification strings that the user can choose [with some limitations][hubit.config.ModelIndexSpecifier].

With the input data and bindings shown above, the content of `_input_consumed` in the `price` function for the car at index 1 will be

```python
{
  'part_counts': [4, 1, 2, 1],
  'part_names':  ['wheel2', 'chassis2', 'bumper', 'engine14']
}
```

i.e. the component's entrypoint function will have all counts and part names for a single car in this case the car at index 1 available in the input.

In the last line of the `price` function, the car price is added to the results

```python
results_provided['car_price'] = result
```

To enable the transfer of the calculated car price to the correct path in the shared results data object we must add a binding for the name `car_price`. If, for example, we want to store the car price in a field called `price` at the same car index as where the input data was taken from, the binding below should be added to the model file.

```yaml
provides_results: 
  - name: car_price # internal name (key) in results_provided
    path: cars[IDX_CAR].price # path in the shared results data
```

The index specifier `IDX_CAR` in the binding path tells `Hubit` to store the car price at the same car index as where the input was taken from. Note that the component itself is unaware of which car (car index) the input represents.

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

Read more about [paths][hubit.config.HubitModelPath], [index specifiers][hubit.config.ModelIndexSpecifier] and index identifiers in the documentation.

### Tips on refactoring

The flexibility of the `Hubit` binding paths allows you to match the interfaces of your existing tools. Further, this flexibility enables you to refactor to get good modularity and optimize for speed when multi-processing is used. Below we will show three versions of the car model and outline some key differences when multi-processing is used.

#### Car model 0

In [`model0.yml`](https://github.com/mrsonne/hubit/blob/master/examples/car/model0.yml) the price calculation receives an entire car object at a specific car index (`IDX_CAR`). This allows the component to store results data on the corresponding car index in the results data object that `Hubit` creates.

```yaml
provides_results: 
  - name: car_price
    path: cars[IDX_CAR].price
consumes_input:
  - name: car
    path: cars[IDX_CAR]
```

This model allows queries such as `cars[:].price` and `cars[1].price`. If car objects in the input data only contains `count` and `name` (like in the example above) this simple model definition is more or less equivalent to the more elaborate model shown above. If, on the other hand, car objects in the input data contains more data this (irrelevant) data would be exposed to the price calculation function. Further, in the implementation of the car price calculation an undesirable tight coupling to the input data structure would be unavoidable. The entrypoint function could look something like this

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

[`model1.yml`](https://github.com/mrsonne/hubit/blob/master/examples/car/model1.yml) is the one described above model 0 where the car price is calculated in a single component i.e. in a single worker process. Such an approach works well if the lookup of parts prices is fast and the car price calculation is also fast. If, however, the lookup is fast while the car price calculation is slow, and we imagine that another component is also consuming the parts prices, then the car price calculation would be a bottleneck. In such cases, separating the lookup from the price calculation would probably boost performance. Models 2 and 3 present two different ways of implementing such a separation.

#### Car model 2

In [`model2.yml`](https://github.com/mrsonne/hubit/blob/master/examples/car/model2.yml) the parts price lookup and the car price calculation are implemented in two separate components. Further, the component that is responsible for the price lookup retrieves the price for one part only. In other words, each lookup will happen in a separate (optionally asynchronous) worker process. When all the lookup processes are done, the price component sums the parts prices to get the total car price. The relevant sections of the model file could look like this

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

In this refactored model `Hubit` will, when submitting a query for the car price using the multi-processor flag, execute each part price calculation in a separate asynchronous worker process. If the part price lookup is fast, the overhead introduced by multi-processing may be render model 2 less attractive. In such cases performing all the lookups in a single component, but still keeping the lookup separate from the car price calculation, as shown in car model 3, could be a good solution.

#### Car model 3

In [`model3.yml`](https://github.com/mrsonne/hubit/blob/master/examples/car/model3.yml) all price lookups take place in one single component and the car price calculation takes place in another component. For the lookup component, the relevant sections of the model file could look like this

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

### Path to the entrypoint function

To tie together the bindings with the the Python code that does the actual work you need to add the path of the Python source code file to the model file. For the first car model it could look like this.

```yaml
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

## Running

To get results from a model requires you to submit a [`query`][hubit.config.Query]. After `Hubit` has processed the query the values of the queried attributes are returned in the _response_. A query may spawn many component workers that may each represent an instance of the same or different model components. Below are two examples of queries and the corresponding responses.

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
{
  'cars[:].parts[:].price': 
  [
    [480.0, 1234.0, 178.0, 2343.0, 45.0],
    [312.0, 1120.0, 178.0, 3400.0]
  ]
}
```

## Rendering

If Graphviz is installed `Hubit` can render models and queries. In the example below we have rendered the query `[cars[0].price]` i.e. the price of the car at index 0.

<a target="_blank" rel="noopener noreferrer" href="https://github.com/mrsonne/hubit/blob/master/examples/car/images/query_car_2.png">
  <img src="https://github.com/mrsonne/hubit/raw/master/examples/car/images/query_car_2.png" width="1000" style="max-width:100%;">
</a>

The graph illustrates nodes in the input data structure, nodes in the the results data structure, the calculation components involved in creating the response as well as hints at which attributes flow in and out of these components. The triple bar icon ≡ indicates that the node is accessed by index and should therefore be a list. The graph was created using the command below.

```python
query = ['cars[0].price']
hmodel.render(query)
```

## Validation

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

## Caching

### Model-level caching

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

The model cache can be cleared using the [`clear_cache`][hubit.model.HubitModel.clear_cache]  method on a `Hubit` model. To check if a model has an associated cached result use [`has_cached_results`][hubit.model.HubitModel.has_cached_results] method on a `Hubit` model. Cached results for all models can be cleared by using [`hubit.clear_hubit_cache()`][hubit.__init__.clear_hubit_cache].

### Component-level caching

Component-level caching can be activated using [set_component_caching][hubit.model.HubitModel.set_component_caching]. By default component-level caching is off. If component-level caching is on, the consumed data for all spawned component workers and the corresponding results will be stored in memory during execution of a query. If `Hubit` finds that, in the same query, two workers refer to the same model component and the input data are identical, the second worker will simply use the results produced by the first worker. The cache is not shared between sequential queries to a model. Also, the component-level cache is not shared between the individual sampling runs using [`get_many`][hubit.model.HubitModel.get_many] method.

The table below comes from printing the log after running car model 2 with and without component-level caching

```python
print(hmodel.log())
```

```
--------------------------------------------------------------------------------------------------
Query finish time    Query took (s)        Worker name        Workers spawned Component cache hits
--------------------------------------------------------------------------------------------------
21-Mar-2021 20:48:26     1.1              car_price                3                 1
                                         part_price               14                 6
21-Mar-2021 20:48:25     1.8              car_price                3                 0
                                         part_price               14                 0
--------------------------------------------------------------------------------------------------
```

The second run (top) uses component-caching and is faster than the first run (bottom).
Both queries spawn 17 workers in order to complete the query, but in the case where
component-caching is active (top) 7 workers reuse results provided by the remaining 10 workers.

For smaller jobs any speed-up obtained my using component-level caching cannot be seen on
the wall clock when using multi-processing. The effect will, however, be apparent in
the model [log][hubit.model.HubitModel.log] as seen above.
