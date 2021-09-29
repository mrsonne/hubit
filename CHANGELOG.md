# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Changed
- Components need be specified under the `components` key in the model file. This **breaks** previous model files.
- The calculation components should be agnostic to the origin of their input. Therefore, entrypoint functions now accept only two arguments namely `_input_consumed` and `results_provided`. Previously three arguments were expected: `_input_consumed`, `_results_consumed` and `results_provided`. Now `_results_consumed` is simply included in `_input_consumed`.
- The format for cache files stored in the folder `.hubit_cache` has changed. To convert old cache files see the example code below. Alternatively, clear the `Hubit` cache using the function `hubit.clear_hubit_cache()`.
- Improved model validation.
- Hyphen is no longer an allowed character for index identifiers. For example this model path is no longer valid `segments[IDX_SEG].layers[IDX-LAY]`.

The example code below converts the cache file `old.yml` to `new.yml`. The file name `old.yml` will, more realistically, be named something like `a70300027991e56db5e3b91acf8b68a5.yml`.


```python
import re
import yaml

with open("old.yml", "r") as stream:
    old_cache_data = yaml.load(stream, Loader=yaml.FullLoader)

# Replace ".DIGIT" with "[DIGIT]" in all keys (paths)
with open("new.yml", "w") as handle:
    yaml.dump(
        {
            re.sub(r"\.(\d+)", r"[\1]", path): val
            for path, val in old_cache_data.items()
        },
        handle,
    )
```
All files in the hubit cache folder `.hubit_cache` should be converted.

### Added
- Support for subscriptions to neiboring compartments (cells, elements). This allows for a sequence of connected and coupled compartments to be calculated based on an initial value e.g. for the first compartment. In other word 0-dimensional and 1-dimensional forward XXX models can be solved. This feature is illustrated in the example with connected tanks where a liquid flows from one tank to the next before reaching the outlet. 
    - Multiple component may share the same entrypoint function.
    - Components that share the same entrypoint function can be scoped using the new field `component.context`.
    - Components may consume specific elements in lists from the input.
    - Allow index offsets in index specifiers. This allows a compartment to refer to e.g. the previous compartment. 
- Fix broken example (`examples/wall/run_precompute.py`)
- Improved performance for input data where only some branches in the input are consumed and where branches are not consumed all the way to the leaves.

Jointly, the first two items allow for sequential calculations dependent calculations. Such cascading dependencies essentially corresponds to a for-loop. See `examples/flow/run.py`.

### Fixed
- The elements of lists that are leaves in the input data tree can now be referenced and queried. 
- Lists of length 1 in input were erroneously interpreted as a simple value 

## [0.3.0] - 2021-05-07
### Changed
- The model configuration format is defined and documented in the `HubitModelConfig` class.
- Introducing `HubitModelConfig` four configuration attributes have been renamed. Therefore, model configuration files used in Hubit 0.3- must be migrated to Hubit 0.3 format. Below is a description of the necessary migrations
    - The top-level object `provides` is now named `provides_results`.
    - The sub-objects `consumes.input` is now a top-level object named `consumes_input`.
    - The sub-objects `consumes.results` is now a top-level object named `consumes_results`.
    - The value of `module_path` should now be specified in the `path` and is interpreted as a path present in `sys.path` that can be imported as a dotted path. 
    The most common use case is a package in `site-packages`. If `path` is a dotted path
    `is_python_path` should be set to `True`.

### Added
- Improved model configuration validation
- Documentation


## [0.2.0] - 2021-03-26
### Added
- Model-level results caching. 
- Component-level results caching. 
- Introduced logging object accessed using `my_hubit_model.log()`. 

## [0.1.0] - 2021-02-28
### Added
- First release
