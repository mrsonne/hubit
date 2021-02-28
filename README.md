[![Build Status](https://travis-ci.com/mrsonne/hubit.svg?branch=master)](https://travis-ci.org/mrsonne/hubit)
[![Coverage Status](https://coveralls.io/repos/github/mrsonne/hubit/badge.svg?branch=master)](https://coveralls.io/github/mrsonne/hubit?branch=master)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

# hubit - a calculation hub  

`hubit` is an event-driven orchestration hub for your existing calculation tools. It allows you to 

- execute calculation tools as one `hubit` composite model with a loose coupling between the model components,
- query the model for specific results thus avoiding explicitly coding (fixed) call graphs and running superfluous calculations,
- make parameter sweeps,
- feed old results into new calculations thus augmenting old results objects,
- easily run your existing tools in asynchronously in multiple processes,
- visualize your `hubit` composite model i.e. visualize your existing tools and the attributes that flow between them.

Compatible with __Python 3.7+__.

## Motivation
Many work places have developed a rich ecosystem of stand-alone tools. These tools may be developed/maintained by different teams using different programming languages and using different input/output data models. Nevertheless, the tools often depend on results provided the other tools leading to complicated and error-prone (manual) workflows.

By defining input and results data structures that are shared between your tools `hubit` allows all your Python-wrappable tools to be seamlessly executed asynchronously as a single model. Asynchronous multi-processor execution often assures a better utilization of the available CPU resources compared to sequential single-processor execution. This is especially true when some time is spent in each component. In practice this performance improvement often compensates the management overhead introduced by `hubit`.
Executing a fixed call graph is faster than executing the same call graph dynamically created by `hubit`. Nevertheless, a fixed call graph will typically encompass all relevant calculations and provide all results, which in many cases will represent wasteful compute since only a subset of the results are actually needed. `hubit` dynamically creates the smallest possible call graph that can provide the results that satisfy the user's query.  

## Getting started

------------------


## Installation & requirement

Install from pypi
```sh
pip install hubit
```


Install from GitHub
```sh
pip install git+git://github.com/mrsonne/hubit.git
```

To render `hubit` models and queries you need to install Graphviz (https://graphviz.org/download/). On e.g. Ubuntu, Graphviz can be installed using the command

```sh
sudo apt install graphviz
```

------------------

## Terminology & example

### Components
To use `hubit` your existing tools each need to be wrapped as a `hubit` _component_. A `hubit` component has bindings to the input data and to the results data. The bindings define which attributes the component

- _consumes_ from the shared input data structure, 
- _consumes_ from the shared results data structure, and 
- _provides_ to the shared results data structure. 

From the bindings `hubit` checks that all required input data and results data is available before a component is executed. The bindings are defined in a _model file_. 

### Component wrapper
As an example imagine that we are calculating the price of a car. Below you can see some pseudo code for the calculation for the car price calculation. The example is available in `examples\car\` 

```python
def price(_input_consumed, _results_consumed, results_provided):
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

The main function in a component (`price` in the example above) should expect the arguments `_input_consumed`, `_results_consumed` and `results_provided` in that order. Results data calculated in the components should only be added to the latter. The values stored in the keys `part_counts` and `part_names` in `_input_consumed` are controlled by the bindings in the model file. 

### Model file & bindings
Before we look at the bindings let us look at the input data. The input can, like in the example below, be defined in a yml file. In the car example the input data is a list containing two cars each with a number of parts

```yml
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

The `price` function above expects a list of part names be stored in the key `part_names` and a list of the corresponding part counts be stored in the key `part_counts`. To achieve this behavior the model file should contain the lines below.

```yml
consumes:
    input:
        - name: part_names # key in component input dict
          path: cars[IDX_CAR].parts[:@IDX_PART].name # path in input data
        - name: part_counts
          path: cars[IDX_CAR].parts[:@IDX_PART].count
```

The strings in square braces are called _index specifiers_. The index specifier `:@IDX_PART` refers to all items for the _index identifier_ `IDX_PARTS`. In this case the specifier contains a slice and an index identifier. The index identifier can be any string that does not include the characters `:` or `@`. The index specifier `IDX_CAR` is actually an index identifier (no `:@` prefix) and refers to a specific car. 

With the input data and bindings shown above, the content of `_input_consumed` in the `price` function for the car at index 1 will be 

```python
{'part_counts': [4, 1, 2, 1], 'part_names':  ['wheel2', 'chassis2', 'bumper', 'engine14']}
```

i.e. the components will have all counts and part names for a single car. The binding should be set up so that the data in `_input_consumed` (and possibly data in `_results_consumed`) suffice to calculate the car price. 

In the last line of the `price` function, the car price is added to the results

```python
results_provided['car_price'] = result
```

In the model file the binding below will make sure that data stored in `results_provided['car_price']` is transferred to a results data object at the same car index as where the input data was taken from.

```yml
provides: 
    - name: car_price # internal name in the component
      path: cars[IDX_CAR].price # path in the shared data model
```

The value in the binding name should match the key used in the component when setting the value on `results_provided`. It is the index specifier `IDX_CAR` in the binding path that tells `hubit` to store the car price at the same car index as where the input was taken from. Note that the component itself is unaware of which car (car index) the input represents. 

Collecting the bindings we get

```yml
provides : 
    - name: car_price # internal name in the component
      path: cars[IDX_CAR].price # path in the shared data model
consumes:
    input:
        - name: part_name
          path: cars[IDX_CAR].parts[:@IDX_PART].name
        - name: part_counts
          path: cars[IDX_CAR].parts[:@IDX_PART].count
```

### Index specifiers & index contexts
`hubit` infers indices and list lengths based on the input data and the index specifiers *defined* for binding paths in the `consumes.input` section. Therefore, index identifiers *used* in binding paths in the `consumes.results` and `provides` sections should always be exist in binding paths in `consumes.input`. 

Further, to provide a meaningful index mapping, the index specifier used in a binding path in the `provides` section should be identical to the corresponding index specifier in the `consumes.input`. The first binding in the example below has a more specific index specifier (for the identifier `IDX_PART`) and is therefore invalid. The second binding is valid.

```yml
provides : 
    # INVALID
    - name: part_name 
      path: cars[IDX_CAR].parts[IDX_PART].name # more specific for the part index

    # VALID: Assign a 'price' attribute each part object in the car object.
    - name: parts_price
      path: cars[IDX_CAR].parts[:@IDX_PART].price # index specifier for parts is equal to consumes.input.path
consumes:
    input:
        - name: part_name
          path: cars[IDX_CAR].parts[:@IDX_PART].name
```

In the invalid binding above, the component consumes all indices of the parts list and therefore storing the price data at a specific part index is not possible. The bindings below are valid since `IDX_PART` is omitted for the bindings in the `provides` section

```yml
provides : 
    # Assign a 'part_names' attribute to the car object. 
    # Could be a a list of all part names for that car
    - name: part_names 
      path: cars[IDX_CAR].part_names # index specifier for parts omitted

    # Assign a 'concatenates_part_names' attribute to the car object.
    # Could be a string with all part names concatenated
    - name: concatenates_part_names 
      path: cars[IDX_CAR].concatenates_part_names # index specifier for parts omitted
consumes:
    input:
        - name: part_name
          path: cars[IDX_CAR].parts[:@IDX_PART].name
```

In addition to defining the index identifiers the input sections also defines index contexts. The index context is the order and hierarchy of the index identifiers. For example an input binding `cars[IDX_CAR].parts[IDX_PART].price` would define both the index identifiers `IDX_CAR` and `IDX_PART` as well as define the index context `IDX_CAR -> IDX_PART`. This index context shows that a part index exists only in the context of a car index. Index identifiers should be used in a unique context i.e. if one input binding defines `cars[IDX_CAR].parts[IDX_PART].price` then defining or using `parts[IDX_PART].cars[IDX_CAR].price` is not allowed.

### Model refactoring

The flexibility in the `hubit` bindings allows you to match the interfaces of your existing tools. Further, this flexibility allows you to refactor your components to get a model with good modularity and allows you to optimize for speed when multi-processing is used. Below we will show three different versions of the car model and outline some key differences in when multi-processing is used.

#### Model 1
Model 1 is the one described above where the car price is calculated in a single component i.e. in a single process. Such an approach works well if the lookup of parts prices is fast and the car price calculation is also fast. If, however, the lookup is fast while the car price calculation is slow, and we imagine that another component is consuming the parts prices, then the car price calculation would be a bottleneck. In such cases, separating the lookup from the price calculation would probably boost performance. Models 2 and 3 present two different ways of implementing such a separation.

#### Model 2
In this version of the model the parts price lookup and the car price calculation functionalities are implemented in two separate components. Further, the component responsible for the price lookup retrieves the price for one part only. In other words, each lookup will happen in a separate asynchronous process. When all the lookup processes are done, the price component sums the parts prices to get the total car price. The relevant sections of the model file could look like this

```yml
- consumes:
    input:
        - name: part_name
          path: cars[IDX_CAR].parts[IDX_PART].name 
        - name: part_count
          path: cars[IDX_CAR].parts[IDX_PART].count
  provides:
        - name: part_price
          path: cars[IDX_CAR].parts[IDX_PART].price

- consumes:
    results:
        - name: prices
          path: cars[IDX_CAR].parts[:@IDX_PART].price
  provides : 
    - name: car_price 
      path: cars[IDX_CAR].price
```

Notice that the first component consumes a specific part index (`IDX_PART`) for a specific car index (`IDX_CAR`). This allows the component to store results data on a specific part index for a specific car index. The first component (price for one component) could look something like this

```python
def part_price(_input_consumed, _results_consumed, results_provided):
    count = _input_consumed['part_count'] 
    name = _input_consumed['part_name'] 
    results_provided['part_price'] = count*my_lookup_function(name)
```

The second component (car price) could look like this

```python
def car_price(_input_consumed, _results_consumed, results_provided):
    results_provided['car_price'] = sum( _results_consumed['prices'] )
```

In this refactored model `hubit` will, when submitting a query for the car price using the multi-processor flag, execute each `part_price` calculation in a separate asynchronous process. If the `part_price` lookup is fast, the overhead introduced by multi-processing may be render model 2 less attractive. In such cases performing all the lookups in a single component, but still keeping the lookup separate from the price calculation, could be a good solution. 

#### Model 3
In this version of the model all lookups take place in one single process and the car price calculation  takes place in another process. For the lookup component, the relevant sections of the model file could look like this

```yml
consumes:
  input:
    - name: parts_name
      path: cars[IDX_CAR].parts[:@IDX_PART].name 
    - name: parts_count
      path: cars[IDX_CAR].parts[:@IDX_PART].count
provides:
  - name: parts_price
    path: cars[IDX_CAR].parts[:@IDX_PART].price
```

Notice that the component consumes all part indices (`:@IDX_PART`) for a specific car index (`IDX_CAR`). This allows the component to store results data on all part indices for a specific car index. The first component (price for one component) could look something like this

```python
def part_price(_input_consumed, _results_consumed, results_provided):
    counts = _input_consumed['parts_count'] 
    names = _input_consumed['parts_name'] 
    results_provided['parts_price'] = [ count*my_lookup_function(name)
                                         for count, name in zip(counts, names) ]
```

In this model, the car price component is identical to the one used in model 2 and is omitted here.

### Paths
To tie together the bindings with the the Python code that does the actual work you need to add the path of the Python source code file to the model file. For the first car model it could look like this.

```yml
- path: ./components/price1.py 
  func_name: price
  provides : 
    - name: car_price
      path: cars[IDX_CAR].price
  consumes:
    input:
      - name: part_names
        path: cars[IDX_CAR].parts[:@IDX_PART].name
      - name: part_counts
        path: cars[IDX_CAR].parts[:@IDX_PART].count
```

The specified path should be relative to model's `base_path`, which defaults to the location of the model file when the model is initialized using the `from_file` method. To specify a module in site packages replace the `path` attribute in the model file with a `module` attribute. This could look like this 

```yml
module: hubit_components.price1
```

where `hubit_components` is a package you have created that contains the module `price1`.

### Running
To get results from a a model requires you to submit a _query_, which tells `hubit` what attributes from the results data structure you want to have calculated. After `hubit` has processed the query, i.e. executed relevant components, the values of the queried attributes are returned in the _response_. Below are two examples of queries and the corresponding responses.

```python
# Load model from file
hmodel = HubitModel.from_file('model1.yml',
                              name='car')

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
print(response)
{'cars[0].price': 4280.0}
```

A query for parts prices for all cars looks like this

```python
query = ['cars[:].parts[:].price']
response = hmodel.get(query)
```

and the corresponding response is

```python
{'cars[:].parts[:].price': [[480.0, 1234.0, 178.0, 2343.0, 45.0],
                            [312.0, 1120.0, 178.0, 3400.0]],
```

## Rendering
If Graphviz is installed `hubit` can render models and queries. In the example below we have rendered the query `cars[0].price` i.e. the price of the car at index 0.

<img src="https://github.com/mrsonne/hubit/blob/develop/examples/car/images/query_car_2.png" width="1000">

The graph illustrates nodes in the input data structure, nodes in the the results data structure, the calculation components involved in creating the response as well as hints at which attributes flow in and out of these components. The triple bar icon ≡ indicates that the node is accessed by index and should therefore be a list. The graph was created using the command below. 

```python
query = ['cars[0].price']
hmodel.render(query)
```

The Examples section below lists more examples that illustrate more `hubit` functionality.

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


# Examples

In the examples all calculation are, for simplicity, carried out directly in the 
hubit component, but the component could just as well wrap a C library, request 
data from a web server or use an installed Python package. The examples are summarized below.

* `examples/car`. This examples encompass the two car models shown above.
* `examples/wall`. This example illustrates heat flow calculations and cost calculations for a wall with two segments. Each wall segment has multiple wall layers that consist of different materials. The example demonstrates model rendering (`run_render.py`) simple queries (`run_queries.py`), reusing previously  calculated results `run_precompute.py`, setting results manually (`run_set_results.py`) and input parameter sweeps (`run_sweep.py`). Most of the wall examples run with or without multi-processing.

To run, for example, the car example execute  

```sh
python -m examples.car.run
```
