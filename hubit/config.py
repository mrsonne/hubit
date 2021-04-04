from __future__ import annotations
from dataclasses import dataclass, field
import yaml
import os
from typing import Dict, Set
from .errors import HubitModelValidationError, HubitModelComponentError

class HubitPath:
    """
    For now just a collection of static methods relating to hubit path 
    validation and manipulation
    """
    @staticmethod
    def validate_path(path: str):
        pass


@dataclass
class HubitBinding:
    """
    Binds an internal component "name" to a "path" in the shared data model
    """

    name: str
    path: str

    def validate(self):
        HubitPath.validate_path(self.path)
        return self

    @classmethod
    def from_cfg(cls, cfg):
        return cls(name=cfg["name"], path=cfg["path"]).validate()


@dataclass
class HubitModelComponent:
    """A model component represent one isolated calculation carried out by
    the function "func_name" located at "path". The function requires
    input from the paths defined in "consumes_input" and
    "consumes_results". The componet delivers results to the paths
    in "provides_results".
    """

    path: str
    func_name: str
    provides_results: Set[HubitBinding]
    consumes_input: Set[HubitBinding] = field(default_factory=set)
    consumes_results: Set[HubitBinding] = field(default_factory=set)
    is_module_path: bool = False

    def validate(self, cfg):
        return self

    @classmethod
    def from_cfg(cls, cfg: Dict) -> HubitModelComponent:

        target_attr = "provides_results"
        try:
            cfg[target_attr] = [
                HubitBinding.from_cfg(binding) for binding in cfg[target_attr]
            ]
        except KeyError:
            raise HubitModelComponentError(
                f'Component with entrypoint "{cfg["func_name"]}" should provide results'
            )

        target_attr = "consumes_input"
        try:
            cfg[target_attr] = [
                HubitBinding.from_cfg(binding) for binding in cfg[target_attr]
            ]
        except KeyError:
            pass

        target_attr = "consumes_results"
        try:
            cfg[target_attr] = [
                HubitBinding.from_cfg(binding) for binding in cfg[target_attr]
            ]
        except KeyError:
            pass

        return cls(**cfg).validate(cfg)

    def does_provide_results(self):
        return len(self.provides_results) > 0

    def does_consume_results(self):
        return len(self.consumes_results) > 0

    def does_consume_input(self):
        return len(self.consumes_input) > 0

    def binding_map(self, binding_type):
        bindings = getattr(self, binding_type)
        return {binding.name: binding.path for binding in bindings}


@dataclass
class HubitModelConfig:
    """Defines the hubit model configuration"""

    components: Set[HubitModelComponent]
    model_file_path: str

    def __post_init__(self):
        # Convert to absolute paths
        self._base_path = os.path.dirname(self.model_file_path)
        for component in self.components:
            if not component.is_module_path:
                component.path = os.path.abspath(
                    os.path.join(self._base_path, component.path)
                )

        self._component_for_name = {
            component.func_name: component for component in self.components
        }

    @property
    def base_path(self):
        return self._base_path

    @property
    def component_for_name(self):
        return self._component_for_name

    def validate(self):
        func_names = [component.func_name for component in self.components]

        if not len(func_names) == len(set(func_names)):
            raise HubitModelValidationError("Component function names must be unique")

        return self

    @classmethod
    def from_file(cls, model_file_path) -> HubitModelConfig:
        with open(model_file_path, "r") as stream:
            cfg = yaml.load(stream, Loader=yaml.FullLoader)
        return cls.from_cfg(cfg, model_file_path)

    @classmethod
    def from_cfg(cls, cfg: Dict, model_file_path: str) -> HubitModelConfig:
        components = [
            HubitModelComponent.from_cfg(component_data) for component_data in cfg
        ]
        return cls(components=components, model_file_path=model_file_path).validate()
