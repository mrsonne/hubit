{% include 'docs/shared/header.html' %}

{% include 'README.md' %}

<!-- # Hubit - a calculation hub  


## Summary

`hubit` is an event-driven orchestration hub for your existing calculation tools. It allows you to 

- execute calculation tools as one `hubit` composite model with a loose coupling between the model components,
- easily run your existing calculation tools in asynchronously in multiple processes,
- query the model for specific results thus avoiding explicitly coding (fixed) call graphs and running superfluous calculations,
- make parameter sweeps,
- feed previously calculated results into new calculations thus augmenting old results objects,
- incremental results caching and calculation restart from cache,
- caching of model component results allowing `hubit` to bypass repeated calculations,
- visualize your `hubit` composite model i.e. visualize your existing tools and the attributes that flow between them.

## Motivation
Many work places have developed a rich ecosystem of stand-alone tools. These tools may be developed/maintained by different teams using different programming languages and using different input/output data models. Nevertheless, the tools often depend on results provided the other tools leading to complicated and error-prone (manual) workflows.

By defining input and results data structures that are shared between your tools `hubit` allows all your Python-wrappable tools to be seamlessly executed asynchronously as a single model. Asynchronous multi-processor execution often assures a better utilization of the available CPU resources compared to sequential single-processor execution. This is especially true when some time is spent in each component. In practice this performance improvement often compensates the management overhead introduced by `hubit`.
Executing a fixed call graph is faster than executing the same call graph dynamically created by `hubit`. Nevertheless, a fixed call graph will typically encompass all relevant calculations and provide all results, which in many cases will represent wasteful compute since only a subset of the results are actually needed. `hubit` dynamically creates the smallest possible call graph that can provide the results that satisfy the user's query. 


## Installation

### From pypi
```sh
pip install hubit
```


### From GitHub
```sh
pip install git+git://github.com/mrsonne/hubit.git
```

To render `hubit` models and queries you need to install Graphviz (https://graphviz.org/download/). On e.g. Ubuntu, Graphviz can be installed using the command

```sh
sudo apt install graphviz
```

### Source

Source code is available at [GitHub](https://github.com/mrsonne/hubit) -->