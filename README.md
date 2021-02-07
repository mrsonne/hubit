# hubit - a calculation hub  

`hubit` is a orchestration hub for your existing calculation tools. It allows you to 

- execute calculation tools as one composite model without coupling them tightly,
- query the model for specific results thus avoiding fixed call trees and superfluous calculations,
- make parameter sweeps,
- feed old results into new calculations,
- run your tools in parallel,
- visualize the composite model.

Compatible with __Python 3.7__.

## Motivation
Often an ecosystem of stand-alone tools exists within a company or department. These tools may be developped by  different teams using different programming laguages and using different input/output formats. Neverthetheless, the tools often depend on results provided the other tools leading to complicated and errorprone (manual) workflows.

By defining input and results data structures shared between your tools `hubit` allows all your Python-wrapable tools to be seamlessly executed asynchronously as a single model. Asynchronous execution
assures a better utilization of the available CPU resources resulting in improved performance compared to sequential execution. In practice this performance improvement compensates the management overhead introduced by `hubit`.

## Getting started



------------------


## Installation & requirement

Install latest package
```sh
pip install hubit
```

Install from GitHub
```sh
XXXXX
```

This will install the requirement which is euivalent to
```sh
pip install graphviz yaml
```

To render the generated DOT source code, you also need to install Graphviz (https://graphviz.org/download/). On e.g.Ubuntu Graphviz can be install using the command
```sh
sudo apt install graphviz
```

------------------


## Workflow

### Wrapping & wiring
A `hubit` _component_ is a tool from your ecosystem wrapped to comply with certain `hubit` standards. A component 

- _consumes_ attributes from the shared input data structure, 
- may _consume_ attributes from the shared results data structure, and 
- _provides_ attributes to the shared results data structure. 

The attributes consumed and provided are defined in a `hubit` _model_ file. To run a model requires the user to provide a _query_, which tells `hubit` what atrributes from the shared results data structure are of of interest. After `hubit` has processed the query, i.e. executed relevant _components_, the values of the queried attributes are returned in the _response_. 

### Examples

In the examples all calculation are, for simplicity, carried out directly in the 
hubit component, but the component could hjust as well wrap a C library or request 
data from a web server.

* `examples/wall`. This example illustrates heat flow calculations and cost calclations for a wall with two segment. Each wall segment has multiple wall layers that consist of different materials. The example demonstrates simple queries, multi-processing, reusing previouly calculated results, setting results manually and input parameter sweeps.