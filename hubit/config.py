from __future__ import annotations
from dataclasses import dataclass, field
import yaml
import os
import re
from typing import Dict, List, Any
from .errors import HubitModelValidationError, HubitModelComponentError


# or inherit from collections import UserString
class HubitQueryPath(str):
    """
    A Hubit query path is used to query a field in the results data. The
    syntax follows general Python syntax for nested objects. Only square
    brackets are allowed and their content is called an index specifier. 
    Index specifiers should be either a positive integer or 
    the character ":".

    Examples
    To query, for example, the attribute "weight" in the 4th element of the list
    "wheels" which is stored on the object "car" use the following
    path "car.wheels[3].weight". The query path "car.wheels[:].weight"
    represents a list where the elements would be the weights for all
    wheels of the car.

    If there are multiple cars stored in a list of cars, the
    query "cars[:].wheels[3].weight" represents a list where the elements
    would be the weights for wheel 4 for all cars. The
    query "cars[:].wheels[:].weight" represents a nested list where the
    each outer list item represents a car and the inner list elements for each
    outer (car) item represent the weights for all wheels for that car.
    """

    char_wildcard = ":"
    regex_idx_spec = r"\[(.*?)\]"
    regex_allowed_idx_spec = "^[:0-9]+$"

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
        assert all(
            [
                idx_spec.isdigit() or idx_spec == HubitQueryPath.char_wildcard
                for idx_spec in idx_specs
            ]
        ), ""

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


class HubitModelPath(HubitQueryPath):
    """
    A Hubit model path is used to reference fields in the input 
    or results data. Model paths are used when constructing  
    model bindings in model components. Compared to a Hubit query path,
    a Hubit model path has different rules for index specifiers. Most 
    importantly an index specifier must contain an index identifier. 
    Index identifiers are used to infer which indices are equivalent in 
    the input and results data and to infer list lengths. This is referred 
    to as index mapping.

    Examples
    Consider the Hubit model path "cars[IDX_CAR].parts[:@IDX_PART].name". As for the 
    query path the strings in square brackets are called index specifiers. 
    The index specifier `:@IDX_PART` refers to all elements of the parts list 
    (the :) and defines an identifier (IDX_PART) for the elements of the parts list.
    So in this case, the index specifier contains both a slice and an index 
    identifier. The index specifier `IDX_CAR` is actually only an index identifier 
    and refers to a specific car. The the Hubit model path 
    "cars[IDX_CAR].parts[:@IDX_PART].name" therefore references the names of 
    all parts of a specific car. A component that consumes this Hubit model path
    would have access to these names. 

    To illustrate the use of the index identifiers for index mapping 
    consider a Hubit model component that consumes the Hubit model 
    path discussed above. The component could use the names for a database 
    lookup to get the prices for each component. If we want hubit to stores 
    these prices in the results, one option would be to store them in a 
    data structure similar to the input. To achieve this behavior the 
    component should provide a  Hubit model path that looks something like
    "cars[IDX_CAR].parts[:@IDX_PART].price". Alternatively, the provided 
    path could be "cars[IDX_CAR].parts_price[:@IDX_PART]". In both cases, 
    the index identifiers allows Hubit to store the part prices for a car 
    at the same car index and parts index as where the input was taken 
    from. Note that the component itself is unaware of which car (car index) 
    the input represents. 
    """

    regex_allowed_idx_ids = "^[a-zA-Z_\-0-9]+$"

    def _validate_index_specifiers(self):
        idx_specs = self.get_index_specifiers()
        assert all(
            [idx_spec.count("@") < 2 for idx_spec in idx_specs]
        ), "Maximum one @ allowed in path"

        # check that if X in [X] contains : then it should be followed by @
        for idx_spec in idx_specs:
            if not HubitModelPath.char_wildcard in idx_spec:
                continue
            idx_wc = idx_spec.index(HubitModelPath.char_wildcard)
            assert idx_spec[idx_wc + 1] == "@", "':' should be followed by an '@'"

    def _validate_index_identifiers(self):
        idx_ids = self.get_index_identifiers()
        # idx_ids can only contain certain characters
        assert all(
            [re.search(HubitModelPath.regex_allowed_idx_ids, idx_id) for idx_id in idx_ids]
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

    def set_indices(self, indices: List[str]) -> HubitModelPath:
        """Replace the index identifiers on the path with location indices

        Args:
            indices (List[str]): Index locations to be inserted into the path.

        Raises:
            AssertionError: If the lengths of indices does not match the length
            the number of index specifiers found in the path.

        Returns:
            HubitModelPath: Path with index identifiers replaced by (string) integers
        """
        _path = str(self)
        # Get all specifiers. Later the specifiers containing a wildcard are skipped
        index_specifiers = self.get_index_specifiers()
        assert len(indices) == len(
            index_specifiers
        ), "The number of indices provided and number of index specifiers found are not the same"
        for index, idx_spec in zip(indices, index_specifiers):

            # Don't replace if there is an index wildcard
            if HubitModelPath.char_wildcard in idx_spec:
                continue

            _path = _path.replace(idx_spec, index, 1)
        return HubitModelPath(_path)

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
        p2 = HubitModelPath.as_internal(self)
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
    path: HubitModelPath

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
        return cls(name=cfg["name"], path=HubitModelPath(cfg["path"])).validate()


@dataclass
class HubitModelComponent:
    """A model component represent one isolated calculation carried out by
    the function "func_name" located at "path". The function requires
    input from the paths defined in "consumes_input" and
    "consumes_results". The componet delivers results to the paths
    in "provides_results".

    Args:
        path (str): Path to the module responsible for the calculation.
        func_name (str): The function name responsible for the calculation. 
        provides_results (List[HubitBinding]): Results provided by the component.
        consumes_input (List[HubitBinding], optional): Input consumed by the components. Defaults to [].
        consumes_results (List[HubitBinding]): XXXXXXXXXXXXXXX. Defaults to [].
        is_module_path (bool, optional): . Defaults to False.
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
