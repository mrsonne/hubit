# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Changed
- The model configuration format is defined and documented in the `HubitModelConfig` class.
- Introducing `HubitModelConfig` four configuration attributes have been renamed. Therefore, model configuration files used in Hubit 0.3- must be migrated to Hubit 0.3 format. Below is a description of the necessary migrations
    - The top-level object `provides` is now named `provides_results`.
    - The sub-objects `consumes.input` is now a top-level object named `consumes_input`.
    - The sub-objects `consumes.results` is now a top-level object named `consumes_results`.
    - The node value of `module_path` should now be specified on the `path` node and is interpreted as a module path if the `is_module_path` is set to `True` 

### Added
- Improved model configuration validation


## [0.2.0] - 2021-03-26
### Added
- Model-level results caching. 
- Component-level results caching. 
- Introduced logging object accessed using `my_hubit_model.log()`. 

## [0.1.0] - 2021-02-28
### Added
- First release