from __future__ import annotations
from dataclasses import dataclass, field
import yaml
import os
import re
from typing import Dict, List, Any
from .errors import HubitModelValidationError, HubitModelComponentError

# or inherit from collections import UserString
class HubitPath(str):
    """
    Hubit path
    """

    idx_wildcard = ":"
    regex_idxid = r"\[(.*?)\]"

    def validate(self):
        pass

    def remove_braces(self) -> str:
        """Remove braces and the enclosed content from the path

        Returns:
            str: path-like string with braces and content removed
        """
        return re.sub("\[([^\.]+)]", "", self)

    def get_index_identifiers(self) -> List[str]:
        """Get the index identifier part of all square braces in the path.

        Returns:
            [type]: [description]
        """
        return [
            index_specifier.split("@")[1] if "@" in index_specifier else index_specifier
            for index_specifier in self.get_index_specifiers()
        ]

    def get_index_specifiers(self) -> List[str]:
        """Get the content of the square braces in the path.

        Returns:
            List: Sequence of index specification strings
        """
        # return re.findall(r"\[(\w+)\]", path) # Only word charaters i.e. [a-zA-Z0-9_]+
        return re.findall(
            HubitPath.regex_idxid, self
        )  # Any character in square brackets

    def set_indices(self, indices: List[str]) -> HubitPath:
        """Replace the index identifiers on the path with
        location indices

        Args:
            indices (List[str]): Sequence of index locations to be inserted into the path.
            The sequence should match the index IDs in the path

        Returns:
            HubitPath: Path with index IDs replaced by (string) integers
        """
        _path = str(self)
        idx_ids = self.get_index_specifiers()
        assert len(indices) == len(
            idx_ids
        ), "The number of indices provided and number of index IDs found are not the same"
        for index, idx_id in zip(indices, idx_ids):

            # Don't replace if there is an index wildcard
            if HubitPath.idx_wildcard in idx_id:
                continue

            _path = _path.replace(idx_id, index, 1)
        return HubitPath(_path)

    @staticmethod
    def as_internal(path: Any) -> str:
        """Convert path using braces [IDX] to internal path using dots .IDX.

        Returns:
            str: internal path-like string
        """
        return path.replace("[", ".").replace("]", "")

    def get_idx_context(self):
        return "-".join(self.get_index_identifiers())

    def paths_between_idxids(self, idxids: List[str]) -> List[str]:
        """Find list of path components inbetween index IDs

        Args:
            idxids (List[str]): Sequence of index identification strings in 'path'

        Returns:
            List[str]: Sequence of index identification strings between index IDs. Includes path after last index ID
        """
        # Remove [] and replace with ..
        p2 = HubitPath.as_internal(self)
        paths = []
        for idxid in idxids:
            # Split at current index ID
            p1, p2 = p2.split(idxid, 1)
            # Remove leading and trailing
            paths.append(p1.rstrip(".").lstrip("."))
        paths.append(p2.rstrip(".").lstrip("."))
        return paths


@dataclass
class HubitBinding:
    """
    Binds an internal component "name" to a "path" in the shared data model
    """

    name: str
    path: HubitPath

    def validate(self):
        self.path.validate()
        return self

    @classmethod
    def from_cfg(cls, cfg):
        return cls(name=cfg["name"], path=HubitPath(cfg["path"])).validate()


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
    provides_results: List[HubitBinding]
    consumes_input: List[HubitBinding] = field(default_factory=list)
    consumes_results: List[HubitBinding] = field(default_factory=list)
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

    components: List[HubitModelComponent]
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
