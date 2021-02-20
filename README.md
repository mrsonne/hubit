# hubit - a calculation hub  

`hubit` is an event-driven orchestration hub for your existing calculation tools. It allows you to 

- execute calculation tools as one composite model with a loose coupling,
- query the model for specific results thus avoiding explicitly coding (fixed) call graphs and running superfluous calculations,
- make parameter sweeps,
- feed old results into new calculations thus augmenting old results objects,
- easily run your existing tools in asynchronously in multiple processes,
- visualize the composite model i.e. your existing tools and the attributes that flow between them.

Compatible with __Python 3.7__.

## Motivation
Many work places have developed a rich ecosystem of stand-alone tools. These tools may be developed/maintained by different teams using different programming languages and using different input/output data models. Nevertheless, the tools often depend on results provided the other tools leading to complicated and error-prone (manual) workflows.

By defining input and results data structures that are shared between your tools `hubit` allows all your Python-wrappable tools to be seamlessly executed asynchronously as a single model. Asynchronous multi-processor execution often assures a better utilization of the available CPU resources compared to sequential execution single-processor. This is especially true when some time is spent in each component. In practice this performance improvement often compensates the management overhead introduced by `hubit`.
Executing a fixed call graph is faster than executing the same call graph dynamically created by `hubit`. Nevertheless, a fixed call graph will typically encompass all relevant calculations and provide all results, which in many cases will represent wasteful compute since only a subset of the results are actually needed. `hubit` dynamically creates the smallest possible call graph that can provide the results that satisfy the user's query.  

## Getting started

------------------


## Installation & requirement

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

From the bindings `hubit` checks that all required input data and results data is available before a component is executed. The bindings are defined in a `hubit` _model file_. 

### Component wrapper
As an example imagine that we are calculating the price of a car. Below you can see some pseudo code for the calulation for the car price calculation. The example is available in `examples\car\` 

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

The main function in a component (`price` in the example above) should expect the arguments `_input_consumed`, `_results_consumed` and `results_provided` in that order. Results data calculated in the components should only be added to the latter. The values corresponding to the keys `part_counts` and `part_names` in `_input_consumed` are controlled by the bindings in the model file. 

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

The `price` function above expects a list of part names stored in the attribute `part_names` and a list of the corresponding part counts stored in the attribute `part_counts`. To achieve this behavior the model file should contain the lines below.

```yml
consumes:
    input:
        - name: part_names # key in component input dict
          path: cars[IDX_CAR].parts[:@IDX_PART].name # path in input data
        - name: part_counts
          path: cars[IDX_CAR].parts[:@IDX_PART].count
```

The strings in square braces are called _index specifiers_. The index specifier `:@IDX_PART` refers to all items for the _index identifier_ `IDX_PARTS`'. In this case the specifier contains a slice and an index identifier. The index identifier can be any string that does not include the characters `:` or `@`. The index specifier `IDX_CAR` is actually an index identifier (no `:@` prefix) and refers to a specific car. 

With the input data and bindings shown above, the content of `_input_consumed` in the `price` function for the car at index 1 will be 

```python
    {'part_counts': [4, 1, 2, 1], 'part_names':  ['wheel2', 'chassis2', 'bumper', 'engine14']}
```

i.e. the components will have all counts and part names for a single car. Inside the component the data in `_input_consumed` (and possibly data in `_results_consumed`) should suffice to calculate the car price. In the last line of the `price` function, the car price is added to the results

```python
    results_provided['car_price'] = result
```

In the model file the binding below will make sure that data stored in `results_provided['car_price']` is transferred to a results data object at the same car index as where the input data was taken from.

```yml
provides: 
    - name: car_price # internal name in the component
      path: cars[IDX_CAR].price # path in the shared data model
```

The value in the binding name should match the key used in the component when setting the value on `results_provided`. It is the index specifier `IDX_CAR` in the binding path that tells `hubit` to store the car price at the same car index as where the input was taken from. Note that the component itself is unaware of which car (car index) the input represents. Collecting the bindings we get

```yml
provides : 
    - name: car_price # internal name in the component
      path: cars[IDX_CAR].price # path in the shared data model
consumes:
    input:
        - name: part_name
          path: cars[IDX_CAR].parts[:@IDX_PART].name
```

### Index specifiers
`hubit` infers indices based on the input data and the index specifiers for the binding paths in the `consumes.input` sections. Therefore, index identifiers used in binding paths in the `consumes.results` and `provides` sections should always be defined in binding paths in the `consumes.input` sections. 

Note that only binding paths that are consumed can contain index specifiers with the prefix `:@`. Binding paths for provided attributes, on the other hand, should always represent a specific location i.e. can only contain pure index identifiers. For this reason the binding below is invalid

```yml
provides : 
    - name: part_price 
      path: cars[IDX_CAR].parts[:@IDX_PART].name # INVALID
consumes:
    input:
        - name: part_name
          path: cars[IDX_CAR].parts[:@IDX_PART].name
```

Further, to provide a meaningful index mapping, the pure index identifiers in the binding paths in the `provides` section should also appear as pure index identifiers in the `consumes.input` section. For this reason the binding below is invalid

```yml
provides : 
    - name: part_price 
      path: cars[IDX_CAR].parts[IDX_PART].name # INVALID
consumes:
    input:
        - name: part_name
          path: cars[IDX_CAR].parts[:@IDX_PART].name
```

Since the component consumes all indices of the parts list, storing the price data at a specific part index is not possible.

### Model refactoring
If the prices for all the car parts are also of interest we can refactor the model to have two components; one component that looks up the price and stores it in the results data and another component that sums the prices. The relevant part of the model file could look like this

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

Notice that the first component consumes a specific part index (`IDX_PART`) for a specific car index (`IDX_CAR`). This allows the component to store results data on a specific part index for a specific car index. The first component (price for each component) could look something like this

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

### Running
After loading the model into `hubit` and the input data set you are ready to run calculations. To get results from a a model requires you to submit a _query_, which tells `hubit` what attributes from the results data structure you want to have calculated. After `hubit` has processed the query, i.e. executed relevant components, the values of the queried attributes are returned in the _response_. Below are two examples of queries and the corresponding responses.

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

The respose looks like this

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

The graph illustrates the input data structure, the results data structure, the calculation components involved in creating the response as well as hints at which attributes flow in and out of these components. The graph was created using the command below

```python
queries = ['cars[0].price']
hmodel.render(queries=queries)
```

The Examples section below lists more examples that illustrate more `hubit` functionality.

# Examples

In the examples all calculation are, for simplicity, carried out directly in the 
hubit component, but the component could just as well wrap a C library, request 
data from a web server or use an installed Python package. The examples are summarized below.

* `examples/car`. This examples encompass the two car models shown above.
* `examples/wall`. This example illustrates heat flow calculations and cost calculations for a wall with two segments. Each wall segment has multiple wall layers that consist of different materials. The example demonstrates simple queries, multi-processing, reusing previously calculated results, setting results manually and input parameter sweeps.

