"""
Objects defined here will automatically be created by `Hubit`. 
Therefore, the class definitions below simply document e.g. the attributes required 
in a model config file or the required structure of a query path.
"""
# https://github.com/mkdocstrings/pytkdocs/issues/69

from __future__ import annotations
from dataclasses import dataclass, field
import pathlib
from collections import abc
import yaml
import re
from typing import Dict, List, Any
from .errors import HubitModelComponentError
from .utils import is_digit

SEP = "."


# or inherit from collections import UserString
class HubitQueryPath(str):
    """
    Reference a field in the results data. The syntax follows general
    Python syntax for nested objects. Only square
    brackets are allowed. The content of the brackets is called an index specifier.
    Currently, index specifiers should be either a positive integer or
    the character `:`. General slicing and negative indices is not supported.

    To query, for example, the attribute `weight` in the 4*th* element of the list
    `wheels`, which is stored on the object `car` use the path
    `car.wheels[3].weight`. The query path `car.wheels[:].weight`
    represents a list with elements being the `weight` for all
    wheels of the car.

    If there are multiple cars stored in a list of cars, the
    query path `cars[:].wheels[3].weight` represents a list where the elements
    would be the weights for the 4*th* wheel for all cars. The
    query path `cars[:].wheels[:].weight` represents a nested list where
    each outer list item represents a car and the corresponding inner list elements
    represent the weights for all wheels for that car.
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
    References a field in the input or results data. Compared to a
    [`HubitQueryPath`][hubit.config.HubitQueryPath],
    a `HubitModelPath` instance has different rules for index specifiers. Most
    importantly an index specifier must contain an index identifier.
    Index identifiers are used to create index mapping and to infer
    list lengths. Index mapping is the mapping indices from lists in
    the input data to equivalent indices in the results data.

    Consider the HubitModelPath instance `cars[IDX_CAR].parts[:@IDX_PART].name`. As for
    query paths, the strings in square brackets are called index specifiers.
    The index specifier `:@IDX_PART` points to all elements (`:`) of the parts list
    and defines an identifier (`IDX_PART`) for elements of the parts list.
    So in this case, the index specifier contains both a slice and an index
    identifier. The left-most index specifier `IDX_CAR` is actually only an index
    identifier and refers to a specific car (no `:@`).
    `cars[IDX_CAR].parts[:@IDX_PART].name` therefore references the names of
    all parts of a specific car. A component that consumes this path
    would have access to these names in a list.

    To illustrate the use of the index identifiers for index mapping
    consider a `Hubit` model component that consumes the path discussed
    above. The component could use the parts names for a database
    lookup to get the prices for each component. If we want `Hubit` to store
    these prices in the results, one option would be to store them in a
    data structure similar to the input. To achieve this behavior the
    component should provide a path that looks something like
    `cars[IDX_CAR].parts[:@IDX_PART].price`. Alternatively, the provided
    path could be `cars[IDX_CAR].parts_price[:@IDX_PART]`. In both cases,
    the index identifiers defined in the input path (`cars[IDX_CAR].parts[:@IDX_PART].name`)
    allows `Hubit` to store the parts prices for a car
    at the same car index and part index as where the input was taken
    from. Note that the component itself is unaware of which car (car index)
    the input represents.

    `Hubit` infers indices and list lengths based on the input data
    and the index specifiers *defined* for binding paths in the `consumes_input` section.
    Therefore, index identifiers *used* in binding paths in the `consumes_results`
    and `provides_results`
    sections should always be exist in binding paths in `consumes_input`.

    Further, to provide a meaningful index mapping, the index specifier
    used in a binding path in the `provides_results` section should be
    identical to the corresponding index specifier in the `consumes_input`.
    The first binding in the example below has a more specific index specifier
    (for the identifier `IDX_PART`) and is therefore invalid. The second
    binding is valid.

    ```yaml
    provides_results:
    # INVALID
    - name: part_name
        path: cars[IDX_CAR].parts[IDX_PART].name # more specific for the part index

    # VALID: Assign a 'price' attribute each part object in the car object.
    - name: parts_price
        path: cars[IDX_CAR].parts[:@IDX_PART].price # index specifier for parts is equal to consumes.input.path
    consumes_input:
    - name: part_name
        path: cars[IDX_CAR].parts[:@IDX_PART].name
    ```

    In the invalid binding above, the component consumes all indices
    of the parts list and therefore storing the price data at a specific part
    index is not possible. The bindings below are valid since `IDX_PART` is
    omitted for the bindings in the `provides_results` section

    ```yaml
    provides_results:
    # Assign a 'part_names' attribute to the car object.
    # Could be a a list of all part names for that car
    - name: part_names
        path: cars[IDX_CAR].part_names # index specifier for parts omitted

    # Assign a 'concatenates_part_names' attribute to the car object.
    # Could be a string with all part names concatenated
    - name: concatenates_part_names
        path: cars[IDX_CAR].concatenates_part_names # index specifier for parts omitted
    consumes_input:
    - name: part_name
        path: cars[IDX_CAR].parts[:@IDX_PART].name
    ```

    ### Index contexts
    In addition to defining the index identifiers the input sections
    also defines index contexts. The index context is the order and hierarchy
    of the index identifiers. For example an input binding
    `cars[IDX_CAR].parts[IDX_PART].price` would define both the index
    identifiers `IDX_CAR` and `IDX_PART` as well as define the index context
    `IDX_CAR -> IDX_PART`. This index context shows that a part index exists
    only in the context of a car index. Index identifiers should be used in a unique
    context i.e. if one input binding defines `cars[IDX_CAR].parts[IDX_PART].price`
    then defining or using `parts[IDX_PART].cars[IDX_CAR].price` is not allowed.

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
            [
                re.search(HubitModelPath.regex_allowed_idx_ids, idx_id)
                for idx_id in idx_ids
            ]
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
        """Convert path using braces [IDX] to internal
        dotted-style path using dots .IDX.

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
    Binds an internal component attribute with `name` to a field
    at `path` in the shared data model

    Args:
        path (HubitModelPath): [`HubitModelPath`][hubit.config.HubitModelPath] pointing to the relevant field in the shared data.
        name (str): Attribute name as it will be exposed in the component.
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
    """Represents one isolated task carried out by
    the function `func_name` located at `path`. The function requires
    input from the paths defined in `consumes_input` and
    `consumes_results`. The componet delivers results to the paths
    in `provides_results`.

    Args:
        path (str): Path to the module responsible for the task. if `is_dotted_path`
            is false the `path` attribute is relative to the `base_path`
            which is the parent path for the model file.
        func_name (str): The function name (entrypoint) that wraps the task.
        provides_results (List[HubitBinding]): [`HubitBinding`][hubit.config.HubitBinding] sequence specifying the results provided by the component.
        consumes_input (List[HubitBinding], optional): [`HubitBinding`][hubit.config.HubitBinding] sequence specifying the input consumed by the input consumed.
        consumes_results (List[HubitBinding]): [`HubitBinding`][hubit.config.HubitBinding] sequence specifying the input consumed by the results consumed.
        is_dotted_path (bool, optional): Set to True if the specified `path` is a dotted path (typically for a package module in site-packages).
    """

    path: str
    provides_results: List[HubitBinding]
    consumes_input: List[HubitBinding] = field(default_factory=list)
    consumes_results: List[HubitBinding] = field(default_factory=list)
    func_name: str = "main"
    is_dotted_path: bool = False

    def __post_init__(self):

        # Set the identifier
        if self.is_dotted_path:
            self._id = f"{self.path}.{self.func_name}"
        else:
            self._id = f"{self.path.replace('.py', '')}.{self.func_name}"

    def validate(self, cfg):
        """
        Validate the object
        """
        return self

    @property
    def id(self):
        return self._id

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
    """Defines the hubit model configuration.

    Args:
        components: [`HubitModelComponent`][hubit.config.HubitModelComponent] sequence.
    """

    components: List[HubitModelComponent]

    # Internal variable used to store the base path
    _base_path: str

    def __post_init__(self):
        # Convert to absolute paths
        for component in self.components:
            if not component.is_dotted_path:
                component.path = pathlib.Path(
                    pathlib.Path(self._base_path).joinpath(component.path)
                ).absolute()

        self._component_for_name = {
            component.id: component for component in self.components
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
        return self

    @classmethod
    def from_file(cls, model_file_path: str) -> HubitModelConfig:
        """
        Create instance from configuration data from a configuration file

        Args:
            model_file_path (str): Path to the configuration file. The
            parent path of `model_file_path` will be used as the `base_path`.

        Returns:
            HubitModelConfig: Object corresponsing to the configuration data
        """
        with open(model_file_path, "r") as stream:
            cfg = yaml.load(stream, Loader=yaml.FullLoader)
        return cls.from_cfg(cfg, pathlib.Path(model_file_path).parent.as_posix())

    @classmethod
    def from_cfg(cls, cfg: Dict, base_path: str) -> HubitModelConfig:
        """
        Create instance from configuration data

        Args:
            cfg: Configuration
            base_path: The path to the model configuration file

        Returns:
            HubitModelConfig: Object corresponsing to the configuration data
        """
        components = [
            HubitModelComponent.from_cfg(component_data) for component_data in cfg
        ]
        return cls(components=components, _base_path=base_path).validate()


@dataclass
class Query:
    """A Hubit query.

    Args:
        paths: [`HubitQueryPath`][hubit.config.HubitQueryPath] sequence.
    """

    paths: List[HubitQueryPath]

    def __post_init__(self):
        for path in self.paths:
            path.validate()

    @classmethod
    def from_paths(cls, paths: List[str]):
        return cls([HubitQueryPath(path) for path in paths])


class FlatData(Dict):
    """
    A key-value pair data representation. Keys represent a path in
    the internal dotted-style. In a dotted-style Hubit path index
    braces [IDX] are represented by dots .IDX.
    """

    def inflate(self) -> Dict:
        """
        Inflate flat data to nested dict. Lists are represented as dicts
        to handle queries that do not include all list elements. For
        example, if the query `["cars[57].price"]` gives the flat data object
        `{"cars.57.price": 4280.0}`, the inflated version is
        `{'cars': {57: {'price': 4280.0}}`. The access syntax
        for the dictionary representation of lists is identical
        to the access syntax had it been a list. Using dictionaries
        we can, however, represent element 57 without adding empty
        elements for the remaining list elements.
        """
        items: Dict[str, Any] = dict()
        for k, v in self.items():
            # path components are strings
            keys = k.split(SEP)
            sub_items = items
            for ki in keys[:-1]:
                _ki = int(ki) if is_digit(ki) else ki
                try:
                    sub_items = sub_items[_ki]
                except KeyError:
                    sub_items[_ki] = dict()
                    sub_items = sub_items[_ki]

            k_last = keys[-1]
            k_last = int(k_last) if is_digit(k_last) else k_last
            sub_items[keys[-1]] = v

        return items

    @classmethod
    def from_dict(cls, dict: Dict, parent_key: str = "", sep: str = "."):
        """
        Flattens dict and concatenates keys to a dotted style internal path
        """
        items = []
        for k, v in dict.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, Dict):
                items.extend(cls.from_dict(v, new_key, sep=sep).items())
            elif isinstance(v, abc.Iterable) and not isinstance(v, str):
                try:
                    # Elements are dicts
                    for idx, item in enumerate(v):
                        _new_key = new_key + "." + str(idx)
                        items.extend(cls.from_dict(item, _new_key, sep=sep).items())
                except AttributeError:
                    # Elements are not dicts
                    items.append((HubitModelPath(new_key), v))
            else:
                items.append((HubitModelPath(new_key), v))
        return cls(items)

    @classmethod
    def from_flat_dict(cls, dict: Dict):
        """
        Create object from a regular flat dictionary
        """
        return cls({HubitModelPath(k): v for k, v in dict.items()})

    def as_dict(self, as_internal_path: bool = False) -> Dict:
        """
        Converts the object to a regular dictionary with string keys

        Args:
            as_internal_path: If False the paths are styled as a HubitModelPath. If True
                the paths are left as internal dotted style.
        """
        d = {str(k): v for k, v in self.items()}
        if not as_internal_path:
            # replace .DIGIT with [DIGIT] using "look behind"
            d = {re.sub(r"\.(\d+)", r"[\1]", k): v for k, v in d.items()}
        return d

    @classmethod
    def from_file(cls, file_path):
        """
        Create object from file
        """
        with open(file_path, "r") as stream:
            data = yaml.load(stream, Loader=yaml.FullLoader)
        return cls.from_flat_dict(data)

    def to_file(self, file_path):
        """
        Write object to file
        """
        with open(file_path, "w") as handle:
            yaml.safe_dump(self.as_dict(as_internal_path=True), handle)
