from __future__ import annotations
from dataclasses import dataclass, field
import yaml
import os
import re
from typing import Dict, List, Any
from .errors import HubitModelValidationError, HubitModelComponentError


class HubitQueryPath(str):
    """
    Hubit query path. Path used to query a field in the results data.

    The syntax follows general Python syntax for nested objects. So to query
    the attribute "attr" in element 7 of the list "the_list" which is stored
    on the object "obj" use the following path "obj.the_list[6].attr". The
    query path "obj.the_list[:].attr" would yield a list where the list
    with elements would have come from "attr" for all elements of the list
    "the_list" which is stored on the object "obj".

    Only square brackets are allowed. The content of the brackets should
    be either a positive integer or the character ":".
    """

    char_wildcard = ":"
    regex_idx_spec = r"\[(.*?)\]"

    @staticmethod
    def balanced(path):
        """
        Check for balanced bracket in string
        """
        opens = "["
        closes = "]"
        pairs = dict(zip(opens, closes))
        _braces = [c for c in path if c in opens or c in closes]
        stack = []
        for c in _braces:
            if c in opens:
                stack.append(c)
            elif len(stack) > 0 and c == pairs[stack[-1]]:
                stack.pop()
            else:
                return False
        return len(stack) == 0

    def _validate_index_specifiers(self):
        idx_specs = self.get_index_specifiers()
        # TODO: allow only only int or :
        return idx_specs

    def _validate_brackets(self):
        # ] should always be followed by a . unless the ] is the last character
        assert all(
            [
                chr_next == "."
                for chr_cur, chr_next in zip(self[:-1], self[1:])
                if chr_cur == "]"
            ]
        ), f"Close brace not folloed by a . in path {self}"

        # Check that braces are balanced
        assert HubitQueryPath.balanced(self), f"Brackets not balanced for path {self}"

    def validate(self):
        self._validate_brackets()
        self._validate_index_specifiers()

    def get_index_specifiers(self) -> List[str]:
        """Get the indexspecifiers from the path i.e. the
        full content of the square braces.

        Returns:
            List: Index specification strings from path
        """
        # return re.findall(r"\[(\w+)\]", path) # Only word charaters i.e. [a-zA-Z0-9_]+
        return re.findall(
            HubitQueryPath.regex_idx_spec, self
        )  # Any character in square brackets


# or inherit from collections import UserString
class HubitPath(HubitQueryPath):
    """
    Hubit model path
    """

    regex_allowed_idx_ids = "^[a-zA-Z_\-0-9]+$"

    def _validate_index_specifiers(self):
        idx_specs = self.get_index_specifiers()
        assert all(
            [idx_spec.count("@") < 2 for idx_spec in idx_specs]
        ), "Maximum one @ allowed in path"

        # check that if X in [X] contains : then it should be followed by @
        for idx_spec in idx_specs:
            if not HubitPath.char_wildcard in idx_spec:
                continue
            idx_wc = idx_spec.index(HubitPath.char_wildcard)
            assert idx_spec[idx_wc + 1] == "@", "':' should be followed by an '@'"

    def _validate_index_identifiers(self):
        idx_ids = self.get_index_identifiers()
        # idx_ids can only contain certain characters
        assert all(
            [re.search(HubitPath.regex_allowed_idx_ids, idx_id) for idx_id in idx_ids]
        ), f"Index identifier must be letters or '_' or '-' for path {self}"

    def validate(self):
        """
        Validate the object
        """
        self._validate_brackets()
        self._validate_index_specifiers()
        self._validate_index_identifiers()

    def remove_braces(self) -> str:
        """Remove braces and the enclosed content from the path

        Returns:
            str: path-like string with braces and content removed
        """
        return re.sub("\[([^\.]+)]", "", self)

    def get_index_identifiers(self) -> List[str]:
        """Get the index identifiers from the path i.e. a
        part of all square braces.

        Returns:
            List[str]: Index identifiers from path
        """
        return [
            index_specifier.split("@")[1] if "@" in index_specifier else index_specifier
            for index_specifier in self.get_index_specifiers()
        ]

    def set_indices(self, indices: List[str]) -> HubitPath:
        """Replace the index identifiers on the path with location indices

        Args:
            indices (List[str]): Index locations to be inserted into the path.

        Raises:
            AssertionError: If the lengths of indices does not match the length
            the number of index specifiers found in the path.

        Returns:
            HubitPath: Path with index identifiers replaced by (string) integers
        """
        _path = str(self)
        # Get all specifiers. Later the specifiers containing a wildcard are skipped
        index_specifiers = self.get_index_specifiers()
        assert len(indices) == len(
            index_specifiers
        ), "The number of indices provided and number of index specifiers found are not the same"
        for index, idx_spec in zip(indices, index_specifiers):

            # Don't replace if there is an index wildcard
            if HubitPath.char_wildcard in idx_spec:
                continue

            _path = _path.replace(idx_spec, index, 1)
        return HubitPath(_path)

    @staticmethod
    def as_internal(path: Any) -> str:
        """Convert path using braces [IDX] to internal path using dots .IDX.

        Returns:
            str: internal path-like string
        """
        return path.replace("[", ".").replace("]", "")

    def get_idx_context(self):
        """
        Get the index context of a path
        """
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
    Binds an internal component attribute with "name" to a field
    at "path" in the shared data model
    """

    name: str
    path: HubitPath

    def validate(self):
        """
        Validate the object
        """
        self.path.validate()
        return self

    @classmethod
    def from_cfg(cls, cfg: Dict) -> HubitBinding:
        """
        Create instance from configuration data

        Args:
            cfg (Dict): Configuration

        Returns:
            HubitBinding: Object corresponsing to the configuration data
        """
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
        """
        Validate the object
        """
        return self

    @classmethod
    def from_cfg(cls, cfg: Dict) -> HubitModelComponent:
        """
        Create instance from configuration data

        Args:
            cfg (Dict): Configuration

        Returns:
            HubitModelComponent: Object corresponsing to the configuration data
        """

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
        """
        Validate the object
        """
        func_names = [component.func_name for component in self.components]

        if not len(func_names) == len(set(func_names)):
            raise HubitModelValidationError("Component function names must be unique")

        return self

    @classmethod
    def from_file(cls, model_file_path: str) -> HubitModelConfig:
        """
        Create instance from configuration data from a configuration file

        Args:
            model_file_path (str): Path to the configuration file

        Returns:
            HubitModelConfig: Object corresponsing to the configuration data
        """
        with open(model_file_path, "r") as stream:
            cfg = yaml.load(stream, Loader=yaml.FullLoader)
        return cls.from_cfg(cfg, model_file_path)

    @classmethod
    def from_cfg(cls, cfg: Dict, model_file_path: str) -> HubitModelConfig:
        """
        Create instance from configuration data

        Args:
            cfg (Dict): Configuration

        Returns:
            HubitModelConfig: Object corresponsing to the configuration data
        """
        components = [
            HubitModelComponent.from_cfg(component_data) for component_data in cfg
        ]
        return cls(components=components, model_file_path=model_file_path).validate()
