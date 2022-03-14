"""
Objects defined here will automatically be created by `Hubit`. 
Therefore, the class definitions below simply document e.g. the attributes required 
in a model config file or the required structure of a query path.
"""
# https://github.com/mkdocstrings/pytkdocs/issues/69

from __future__ import annotations, with_statement
import copy
from abc import ABC, abstractproperty
from dataclasses import dataclass, field
import pathlib
from collections import abc, Counter
import yaml
import re
from typing import (
    Dict,
    List,
    Any,
    Tuple,
    Sequence,
    Union,
    Optional,
    TypeVar,
    cast,
)
from .errors import HubitError, HubitModelComponentError
from .utils import is_digit

SEP = "."


class PathIndexRange(str):
    """
    In [`HubitModelPath`][hubit.config.HubitModelPath] and
    [`HubitQueryPath`][hubit.config.HubitQueryPath]  the
    supported ranges comprise

    - Positive integers e.g. `0`, `17`.
    - Negative integers e.g. `-1`, `-2`.
    - The all-index character `:`.

    Further, in the `index_scope` attribute of
    [`HubitModelComponent`][hubit.config.HubitModelComponent] the following
    ranges are also allowed

    - `d:` where `d` is a positive integer e.g. `3:`.
    - `:d` where `d` is a positive integer e.g. `:3`.
    - `d1:d2` where `d1` and `d2` are positive integers and `d1` < `d2` e.g. `2:5`
    """

    wildcard_chr = ":"

    def _is_limited_range(value: str) -> bool:

        # Must contain wildcard_chr
        if PathIndexRange.wildcard_chr in value:
            # At least start or end should be a digit (one could be empty)
            start, end = value.split(PathIndexRange.wildcard_chr)
            if is_digit(start) or is_digit(end):
                return True
            else:
                return False
        else:
            return False

    def __new__(
        self,
        value,
        allow_limited_range: bool = True,
        allow_negative_index: bool = True,
    ):
        return super().__new__(self, value)

    def __init__(
        self,
        value,
        allow_limited_range: bool = True,
        allow_negative_index: bool = True,
    ):
        super().__init__()
        self.allow_limited_range = allow_limited_range
        self.allow_negative_index = allow_negative_index

        # Determine the range type
        self.is_digit = False
        self.is_empty = False
        self.is_full_range = False
        self.is_limited_range = False
        if is_digit(value):
            self.is_digit = True
        elif value == "":
            self.is_empty = True
        elif value == self.wildcard_chr:
            self.is_full_range = True
        elif PathIndexRange._is_limited_range(value):
            self.is_limited_range = True
        else:
            raise HubitError(f"Unknown range format '{self}'")

        self._validate()

    @property
    def is_counted_from_back(self):
        """Is the range counted from the back end"""
        return self.is_digit and int(self) < 0

    @property
    def start(self) -> Union[int, None]:
        """First index in range"""
        if self.is_digit:
            return int(self)
        elif self.is_empty:
            None
        elif self.is_full_range:
            return 0
        elif self.is_limited_range:
            start, _ = self.split(self.wildcard_chr)
            if start == "":
                return 0
            elif is_digit(start):
                return int(start)
        return None

    def _validate_digit(self):
        if not self.allow_negative_index and int(self) < 0:
            raise HubitError(f"Index '{self}' should be positive")

    def _validate_limited_range(self):

        if not self.allow_limited_range:
            raise HubitError(
                f"Limited range is not allowed here. Found range '{self}'."
            )

        start, end = self.split(self.wildcard_chr)

        if not (start == "" or is_digit(start)):
            raise HubitError(
                f"Invalid range '{self}'. Range start '{start}' should be digit or empty"
            )

        if not (end == "" or is_digit(end)):
            raise HubitError(
                f"Invalid range '{self}'. Range end '{end}' should be digit or empty"
            )

        if is_digit(start) and int(start) < 0:
            raise HubitError(
                f"Invalid range '{self}'. Range start '{start}' should be positive"
            )

        if is_digit(end) and int(end) < 0:
            raise HubitError(
                f"Invalid range '{self}'. Range end '{end}' should be positive"
            )

        if is_digit(start) and is_digit(end) and int(start) > int(end):
            raise HubitError(
                f"Invalid range '{self}'. Range start '{start}' greater that range end '{end}'"
            )

    def _validate(self):
        if self.is_digit:
            self._validate_digit()
        elif self.is_limited_range:
            self._validate_limited_range()

    def _lrange_intersects_digit(self, idx: int) -> bool:
        """Must be one limited range and digit.Not validated."""
        # postpone casting from string to int until we know it can be done
        start, end = self.split(self.wildcard_chr)

        if start == "":
            is_in_lower = True
        else:
            is_in_lower = idx >= int(start)

        if end == "":
            is_in_upper = True
        else:
            is_in_upper = idx < int(end)

        return is_in_lower and is_in_upper

    def _lrange_intersects_lrange(self, other: PathIndexRange) -> bool:
        """Must be two limited ranges. This assumption
        must be validated outside this method.
        """
        start1: Union[str, int]
        start2: Union[str, int]
        end1: Union[str, int]
        end2: Union[str, int]
        start1, end1 = self.split(self.wildcard_chr)
        start2, end2 = other.split(self.wildcard_chr)

        # Replace 'no limit' (from the start) with 0
        if start1 == "":
            start1 = 0
        if start2 == "":
            start2 = 0

        start1 = int(start1)
        start2 = int(start2)

        if end1 == "":
            if end2 == "":
                # ooooo|---------->
                # oo|------------->
                return True
            elif start1 < int(end2):
                # ooooooo|-------->
                # oo|-------|oooooo
                return True
            else:
                # ooooooo|-------->
                # o|--|oooooooooooo
                return False

        if end2 == "":
            if start2 < int(end1):
                # oo|-------|oooooo
                # ooooooo|-------->
                return True
            else:
                # o|--|oooooooooooo
                # ooooooo|-------->
                return False

        # Ends can safely be cast as int
        end1 = int(end1)
        end2 = int(end2)

        # The >= (instead of just >) behaves as standard Python
        if start1 >= end2:
            # oooooooo|--|oo
            # oo|-----|ooooo
            return False
        elif start2 >= end1:
            # oo|-----|ooooo
            # oooooooo|--|oo
            return False
        else:
            return True

    def includes(self, range: PathIndexRange):
        """Is the specified range a subset of self"""
        if self.is_empty:
            return True

        if range.is_full_range:
            return self.is_full_range
        elif range.is_digit:
            return self.contains_index(int(range))
        elif range.is_empty:
            return True
        elif range.is_limited_range:
            raise NotImplementedError("Limited ranges not allowed in paths")

    def contains_index(self, idx: int) -> bool:
        """integer contained in range"""
        if self.is_limited_range:
            return self._lrange_intersects_digit(idx)
        elif self.is_digit:
            return str(idx) == self
        elif self.is_full_range:
            return True
        elif self.is_empty:
            return True
        else:
            raise HubitError(f"Unknown range '{self}'")

    def intersects(
        self, other: PathIndexRange, allow_self_empty: bool = False
    ) -> Optional[bool]:
        """The intersection between the two ranges

        Scenarios

             self               D  L  F  Empty
        other
                  Digit (D)     2  4  1  6
                  Limited (L)   3  5  1  6
                  Full (F)      1  1  1  6
        """
        if self.is_full_range or other.is_full_range:
            # Scenario 1: At least one range covers all indices so
            # there must be an an intersection
            return True
        elif self.is_digit and other.is_digit:
            # Scenario 2: Both range are indices so they must be
            # equal for a non-empty intersection
            return self == other
        elif self.is_digit and other.is_limited_range:
            # Scenario 3: self is digit, other is limited
            return other._lrange_intersects_digit(int(self))
        elif other.is_digit and self.is_limited_range:
            # Scenario 4: self is limited, other is digit
            return self._lrange_intersects_digit(int(other))
        elif other.is_limited_range and self.is_limited_range:
            # Scenario 5:
            self._lrange_intersects_lrange(other)
        elif allow_self_empty and self.is_empty:
            # Scenario 6: If a model path has an empty range e.g. list[IDX]
            # it will always intersect list[DIGIT], list[DIGIT1:DIGIT2] and list[:]
            return True
        else:
            raise HubitError(
                f"Cannot find intersection for unknown range combination `{self}` and `{other}`"
            )
        return None


class _IndexSpecifier(ABC, str):
    # TODO: Warning metaclass with abstract methods
    # abc and multiple inheritance... https://stackoverflow.com/questions/37398966/python-abstractmethod-with-another-baseclass-breaks-abstract-functionality

    @abstractproperty
    def range(self) -> PathIndexRange:
        pass

    @abstractproperty
    def identifier(self) -> str:
        pass

    @abstractproperty
    def offset(self) -> int:
        pass


class QueryIndexSpecifier(_IndexSpecifier):
    """
    Index specifiers for [`HubitQueryPath`][hubit.config.HubitQueryPath].
    Currently, index specifiers should be either a positive integer or
    the character `:`. General slicing is not supported.
    """

    @property
    def range(self) -> PathIndexRange:
        return PathIndexRange(self)

    @property
    def identifier(self) -> str:
        return ""

    @property
    def offset(self) -> int:
        return 0


class ModelIndexSpecifier(_IndexSpecifier):
    """
    Index specifiers for [`HubitModelPath`][hubit.config.HubitModelPath].
    A model path index specifier is composed of three parts namely the
    _range_, the _identifier_ and the _offset_, in that order. The
    structure of an model index specifier is "`range @ identifier offset`" with
    spaces added to increase clarity.

    - The _identifier_ is used internally map an index in input lists to
    the equivalent index in the results. Can be any string of characters in
    a-z, A-Z, digits as well as _ (underscore). An example could be `MYIDX`, which
    would refer to one index in a list.
    - The _range_ must conform with [`PathIndexRange`][hubit.config.PathIndexRange]
    and may be used
    to control the scope of an _identifier_. An example could be `0` or `:`.
    - The _offset_ is a signed integer that may be used to offset the affected
    index. An example could be `-1`.

    Using the examples above the model index specifier would be `:@MYIDX-1`.
    The _range_ and last are optional. A non-empty _range_ requires an empty
    (i.e. zero) _offset_ and vice versa.

    To put index specifiers into some context
    consider a Hubit component that provides `cars[IDX_CAR].parts[:@IDX_PART].name`.
    This path tells Hubit that the names of all parts of a specific car can
    be provided.
    Let us break down the path and take a closer look at the index specifers in
    square brackets.
    The _index specifier_ `:@IDX_PART` refers to all elements of the parts list
    (using the _range_ `:`) and defines the _identifier_ (`IDX_PART`) to represent
    elements of the parts list.
    So in this case, the index specifier contains both a range and an
    identifier, but no offset.
    The left-most index specifier `IDX_CAR` only contains an
    _identifier_ that represents elements of the cars list. Since no _range_
    is specified the _identifier_ refers to a specific car determined by
    the query (e.g. `cars[6].parts[:].name`).
    `cars[IDX_CAR].parts[:@IDX_PART].name` therefore references the names of
    all parts of a specific car which depend on the query specified by the user.
    A component that consumes this path would have access to these names in a list.
    The index specifier `0@IDX_PART` would always reference element 0 of the
    parts list irrespective of the query.
    """

    ref_chr = "@"
    wildcard_chr = PathIndexRange.wildcard_chr
    # Characters a-z, A-Z, _ and digits are allowed
    regex_allowed_identifier = r"^[a-zA-Z_0-9]+$"

    def __new__(
        self, value, allow_limited_range: bool = True, allow_negative_index: bool = True
    ):
        return super().__new__(self, value)

    def __init__(
        self, value, allow_limited_range: bool = True, allow_negative_index: bool = True
    ):
        super().__init__()
        self.allow_limited_range = allow_limited_range
        self.allow_negative_index = allow_negative_index

    def validate(self):
        assert (
            self.count(self.ref_chr) < 2
        ), f"Maximum one '{self.ref_chr}' allowed in index specifier '{self}'"

        # Getting the range will trigger validation
        self.range

        # check that if @ is present the idx_range is non-empty
        if self.ref_chr in self:
            assert (
                not self.range.is_empty
            ), f"Found '{self.ref_chr}' but no range was specified in '{self}'."

        assert (
            self._validate_cross()
        ), f"Invalid index specifier '{self}'. A non-empty range requires an empty (i.e. zero) offset and vice versa."

        assert (
            self._validate_identifier()
        ), f"Invalid index identifier '{self.identifier}' for index specifier {self}. Must be letters or '_'."

        assert (
            self._validate_offset()
        ), f"Invalid offset '{self.offset}' for index specifier {self}."

    def _validate_cross(self):
        """A non-empty range requires an empty (i.e. zero) offset and vice versa"""
        return not (self.offset != 0 and not self.range.is_empty)

    def _validate_identifier(self):
        return re.search(self.regex_allowed_identifier, self.identifier)

    def _validate_offset(self):
        return is_digit(self.offset)

    @property
    def range(self) -> PathIndexRange:
        return (
            PathIndexRange(
                self.split(self.ref_chr)[0],
                allow_limited_range=self.allow_limited_range,
                allow_negative_index=self.allow_negative_index,
            )
            if self.ref_chr in self
            else PathIndexRange("")
        )

    @property
    def identifier(self) -> str:
        # remove the (signed) offset
        idx_spec = self.replace("{0:+d}".format(self.offset), "")
        return idx_spec.split(self.ref_chr)[1] if self.ref_chr in idx_spec else idx_spec

    @property
    def offset(self) -> int:
        try:
            return int(self[self.index("+") :])
        except ValueError:
            pass

        try:
            return int(self[self.index("-") :])
        except ValueError:
            return 0

    @classmethod
    def from_components(cls, identifier, idx_range: str = "", offset: int = 0):
        """Create index specifier from from components. Only identifier is required"""
        if offset == 0:
            _offset = ""

        if not idx_range == "":
            _idx_range = f"{idx_range}{cls.ref_chr}"

        return cls(f"{_idx_range}{identifier}{_offset}")


Path = Union["HubitModelPath", "HubitQueryPath"]

# upper bound types
# Path = TypeVar("Path", bound="_HubitPath") # gives issues with init LengthTree._prune_path
IndexSpecifier = TypeVar("IndexSpecifier", bound="_IndexSpecifier")


class _HubitPath(str):
    wildcard_chr = PathIndexRange.wildcard_chr

    # Any sequence of characters in square brackets excluding the brackets
    regex_idx_spec = r"\[(.*?)\]"
    # Any sequence of characters in square braces including the braces
    regex_braces = r"\[.*?\]"

    @property
    def index_context(self):
        raise NotImplementedError

    @staticmethod
    def as_internal(path: Any) -> str:
        """Convert path using braces [IDX] to internal
        dotted-style path using dots .IDX.

        Returns:
            str: internal path-like string
        """
        return path.replace("[", ".").replace("]", "")

    @classmethod
    def from_dotted(cls, dotted_string: str) -> Any:
        # replace .DIGIT with [DIGIT] using "look behind"
        # Match is source string is .DIGIT but the capturing group is
        # DIGIT which is used in the target string as [DIGIT]
        return cls(re.sub(r"\.(\d+)", r"[\1]", dotted_string))

    @staticmethod
    def balanced(path):
        """
        Check for balanced bracket in string
        """
        opens = "["
        closes = "]"
        pairs = dict(zip(opens, closes))
        _braces = [c for c in path if (c in opens) or (c in closes)]
        stack = []
        for c in _braces:
            if c in opens:
                stack.append(c)
            elif len(stack) > 0 and c == pairs[stack[-1]]:
                stack.pop()
            else:
                return False
        return len(stack) == 0

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
        assert _HubitPath.balanced(self), f"Brackets not balanced for path {self}"

    def components(self):
        return self.as_internal(self).split(".")

    def new_with_index(self, idxspec: IndexSpecifier, index: str) -> Path:
        """
        Replace the first index specifier (idxspec) with the index
        """
        return cast(Path, self.__class__(self.replace(f"[{idxspec}]", f"[{index}]", 1)))

    def set_indices(self, indices: Sequence[str], mode: int = 0) -> _HubitPath:
        """Replace the index specifiers on the path with location indices

        Args:
            indices (List[str]): Index locations to be inserted into the path.
            mode (int): 0: replace all
                        1: do not replace if wildcard found in index specifier
                        2: only replace if wildcard found in index specifier

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
        length_open_and_close_braces = 2
        start = 0
        for index, idx_spec in zip(indices, index_specifiers):
            # Don't replace if there is an index wildcard
            if mode > 0:
                if mode == 1 and self.wildcard_chr in idx_spec:
                    continue
                elif mode == 2 and self.wildcard_chr not in idx_spec:
                    continue

            # replace starting from index 0 in the string. Always move forward i.e.
            # a simple replace will not always work
            start = _path.find(f"[{idx_spec}]", start)
            _path = (
                _path[:start]
                + f"[{index}]"
                + _path[start + len(idx_spec) + length_open_and_close_braces :]
            )
            start += 1
        return self.__class__(_path)

    def get_index_specifiers(self) -> List[Any]:
        """Get the index specifiers from the path i.e. the
        full content of the square braces.

        Returns:
            List: Index specification strings from path
        """
        pass

    def remove_braces(self) -> str:
        """Remove braces and the enclosed content from the path

        Returns:
            str: path-like string with braces and content removed
        """
        return re.sub(_HubitPath.regex_braces, "", self)

    def field_names(self) -> List[str]:
        """Find list of path components in between index specifiers
        i.e. the field names

        Returns:
            List[str]: Sequence of field names
        """
        return self.remove_braces().split(SEP)

    def has_slice_range(self):
        """Check if path has a slice that is a range"""
        return self.wildcard_chr in self

    def ranges(self) -> List[PathIndexRange]:
        """Get the ranges from the path i.e. the part of all square braces preceding the @.

        Returns:
            Ranges from path
        """
        return [idx_spec.range for idx_spec in self.get_index_specifiers()]

    def paths_between_specifiers(self) -> List[str]:
        """Find list of path components in between index specifiers

        Returns:
            Sequence of path strings between index
            specifers. Includes path after last index specifier
        """
        return re.split(f"{_HubitPath.regex_braces}.|{_HubitPath.regex_braces}", self)


class HubitQueryPath(_HubitPath):
    """
    Reference a field in the results data. The syntax follows general
    Python syntax for nested objects. Only square
    brackets are allowed. The content of the brackets is called an
    index specifier and must comply with
    [`QueryIndexSpecifier`][hubit.config.QueryIndexSpecifier].

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

    regex_allowed_idx_spec = "^[:0-9]+$"

    def _validate_index_specifiers(self):
        assert all(
            [
                is_digit(idx_spec) or idx_spec == HubitQueryPath.wildcard_chr
                for idx_spec in self.get_index_specifiers()
            ]
        ), f"Invalid index specifier found in: {', '.join(idx_spec for idx_spec in self.get_index_specifiers())}"

    def validate(self):
        self._validate_brackets()
        self._validate_index_specifiers()

    def set_indices(self, indices: Sequence[str], mode: int = 0) -> HubitQueryPath:
        """Change the return type compared to the super class"""
        return self.__class__(super().set_indices(indices, mode))

    # def set_slice(self, indices: List[str]) -> HubitQueryPath:
    #     _path = str(self)
    #     # Get all specifiers. Later the specifiers containing a wildcard are skipped
    #     index_specifiers = self.get_index_specifiers()
    #     assert len(indices) == len(
    #         index_specifiers
    #     ), "The number of indices provided and number of index specifiers found are not the same"
    #     for index, idx_spec in zip(indices, index_specifiers):
    #         # Don't replace if there is an index wildcard
    #         if self.wildcard_chr in idx_spec:
    #             continue
    #         _path = _path.replace(idx_spec, index, 1)
    #     return self.__class__(_path)

    def field_names_match(self, model_path: HubitModelPath) -> bool:
        """Check if the field names in query match the field names
        in the model path
        """
        if self.remove_braces() != model_path.remove_braces():
            return False
        else:
            return True

    def index_specifiers_match(self, model_path: HubitModelPath) -> bool:
        """Check if the index specifiers in query intersect the index
        specifiers in the model path
        """
        q_specifiers = self.get_index_specifiers()
        m_specifiers = model_path.get_index_specifiers()
        if len(q_specifiers) != len(m_specifiers):
            return False

        for qspec, mspec in zip(q_specifiers, m_specifiers):
            if not mspec.range.intersects(qspec.range, allow_self_empty=True):
                return False
        return True

    def path_match(self, model_path: HubitModelPath) -> bool:
        """Check if the query matches the model path from the
        model bindings

        Args:
            model_path: A model path (provider)
            check_intersection: Should the intersection between the index specifiers be checked

        Returns:
            bool: True if the query matches the model path
        """
        if not self.field_names_match(model_path):
            return False
        else:
            return self.index_specifiers_match(model_path)

    def idxs_for_matches(
        self, mpaths: List[HubitModelPath], check_intersection: bool = True
    ) -> List[int]:
        """
        Returns indices in the sequence of provider strings that match the
        structure of the query string
        """
        feval = self.path_match if check_intersection else self.field_names_match
        return [idx for idx, mpath in enumerate(mpaths) if feval(mpath)]

    def get_index_specifiers(self) -> List[QueryIndexSpecifier]:
        items = re.findall(_HubitPath.regex_idx_spec, self)
        return [QueryIndexSpecifier(item) for item in items]

    @property
    def has_negative_indices(self):
        return any(range_.is_counted_from_back for range_ in self.ranges())


class _HubitQueryDepthPath(HubitQueryPath):
    """
    A `_HubitQueryDepthPath` specifies the maximum depth that can
    be queried and referenced from a [`HubitModelPath`][hubit.config.HubitModelPath].
    Compared to a [`HubitQueryPath`][hubit.config.HubitQueryPath] the index specifiers
    for a `_HubitQueryDepthPath` can only be an asterisk (*) signifying
    "any" index.

    If, for example a `_HubitQueryDepthPath` is specified as `cars` in the
    [`HubitModelConfig`][hubit.config.HubitModelConfig] only the full list
    of car objects are available for component consuming the `car`
    `HubitModelPath`. Queries for `cars[0]` or `cars[:]` will not work.

    If a `_HubitQueryDepthPath` is specified as `cars[*]` whole car objects
    will available a for components consuming e.g. `cars[IDX_CAR]`.
    Queries for `cars[0]` or `cars[:]` will work.

    `cars[*].wheels[*]`. No query such as `cars[:].wheels[:].weight`
    wheels object transferred
    """

    idx_wildcard = "*"

    def _validate_index_specifiers(self):
        idx_specs = self.get_index_specifiers()
        assert all(
            [idx_spec == _HubitQueryDepthPath.idx_wildcard for idx_spec in idx_specs]
        ), f"Unexpected index specifier found in {self.__class__.__name__} with value {self}"

    def validate(self):
        self._validate_brackets()
        self._validate_index_specifiers()

    def compile_regex(self):
        """Convert to internal path but escaping dots"""
        return re.compile(
            self.replace("[", r"\.")
            .replace("]", r"")
            .replace(_HubitQueryDepthPath.idx_wildcard, "[0-9]+")
        )


class HubitModelPath(_HubitPath):
    """
    References a field in the input or results data. Compared to a
    [`HubitQueryPath`][hubit.config.HubitQueryPath],
    a `HubitModelPath` instance has different rules for index
    specifiers (see [`ModelIndexSpecifier`][hubit.config.ModelIndexSpecifier]).

    To illustrate the use of the index identifiers for index mapping
    in a model path consider a `Hubit` model component that consumes
    the path `cars[IDX_CAR].parts[:@IDX_PART].name` (as discussed
    [`here`][hubit.config.ModelIndexSpecifier])).
    The component could use the parts names for a database
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
        path: cars[IDX_CAR].parts[:@IDX_PART].price # index specifier for parts
            is equal to consumes.input.path
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

    def __new__(self, value: str = "", allow_limited_range: bool = True):
        return super().__new__(self, value)

    def __init__(self, value: str = "", allow_limited_range: bool = True):
        super().__init__()
        self.allow_limited_range = allow_limited_range
        self.allow_negative_index = True

    def _validate_index_specifiers(self):
        for idx_spec in self.get_index_specifiers():
            idx_spec.validate()

    def validate(self):
        """
        Validate the object
        """
        self._validate_brackets()
        self._validate_index_specifiers()

    def get_index_specifiers(self) -> List[ModelIndexSpecifier]:
        items = re.findall(_HubitPath.regex_idx_spec, self)
        return [
            ModelIndexSpecifier(
                item, self.allow_limited_range, self.allow_negative_index
            )
            for item in items
        ]

    def get_index_identifiers(self) -> List[str]:
        """Get the index identifiers from the path i.e. the
        part of all square braces after the @ (if any) else the
        whole content of the square braces.

        Returns:
            List[str]: Index identifiers from path
        """
        return [idx_spec.identifier for idx_spec in self.get_index_specifiers()]

    def range_for_identifiers(self) -> Dict[str, PathIndexRange]:
        """Return dict with the range for each identifier in the path"""
        return {
            idx_spec.identifier: idx_spec.range
            for idx_spec in self.get_index_specifiers()
        }

    def set_indices(self, indices: Sequence[str], mode: int = 0) -> HubitModelPath:
        """Change the return type compared to the super class"""
        return self.__class__(super().set_indices(indices, mode))

    def set_range_for_idxid(self, value_for_idxid: Dict[str, Any]) -> HubitModelPath:
        # Get current values
        idx_specs = self.get_index_specifiers()
        idx_ids = self.get_index_identifiers()

        # Loop over input value for index ID
        for idxid, range in value_for_idxid.items():

            # Which index of index specier are we replacing
            idx = idx_ids.index(idxid)

            # Construct and set the index specifier
            idx_specs[idx] = ModelIndexSpecifier.from_components(
                idxid, idx_range=str(range)
            )
        return self.set_indices(idx_specs)

    def as_query_depth_path(self):
        return _HubitQueryDepthPath(re.sub(HubitModelPath.regex_braces, "[*]", self))

    def as_include_pattern(self):
        return self.remove_braces()

    @property
    def index_context(self):
        """
        Get the index context of a path
        """
        return "-".join(self.get_index_identifiers())


@dataclass
class HubitBinding:
    """
    Binds an internal component attribute with `name` to a field
    at `path` in the shared data model

    Args:
        path (HubitModelPath): [`HubitModelPath`][hubit.config.HubitModelPath]
            pointing to the relevant field in the shared data.
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
            HubitBinding: Object corresponding to the configuration data
        """

        # Do not allow limited index ranges in binding paths
        try:
            return cls(
                name=cfg["name"],
                path=HubitModelPath(
                    cfg["path"],
                    allow_limited_range=False,
                ),
            ).validate()
        except HubitError as err:
            name = cfg["name"]
            path = cfg["path"]
            raise HubitError(
                f"Error while processing binding with name '{name}' and path '{path}': {str(err)}"
            )


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
        provides_results (List[HubitBinding]): [`HubitBinding`][hubit.config.HubitBinding]
            sequence specifying the results provided by the component. The names
            in the bindings must be unique within `provides_results` for the component.
        consumes_input (List[HubitBinding], optional): [`HubitBinding`][hubit.config.HubitBinding]
            sequence specifying the input consumed by the component. The names
            in the bindings must be unique within `consumes_input` and `consumes_results`
            for the component.
        consumes_results (List[HubitBinding]): [`HubitBinding`][hubit.config.HubitBinding]
            sequence specifying the input consumed by the component. The names
            in the bindings must be unique within `consumes_input` and `consumes_results`
            for the component.
        index_scope (dict, optional): A map from the index identifiers to an index. Used to
            limit the scope of the component. If, for example, the scope
            is `{IDX_TANK: 0}` the component is only used when the value of the
            index identifier IDX_TANK is 0. The scope can only have one element.
            Values must comply with [`PathIndexRange`][hubit.config.PathIndexRange].
        is_dotted_path (bool, optional): Set to True if the specified `path` is a
            dotted path (typically for a package module in site-packages).
    """

    # _index (int): Component index in model file

    path: str
    provides_results: List[HubitBinding]
    _index: int
    consumes_input: List[HubitBinding] = field(default_factory=list)
    consumes_results: List[HubitBinding] = field(default_factory=list)
    func_name: str = "main"
    is_dotted_path: bool = False
    index_scope: Dict[str, PathIndexRange] = field(default_factory=dict)

    def __post_init__(self):

        # Set the identifier & name
        if self.is_dotted_path:
            self._name = f"{self.path}.{self.func_name}"
        else:
            self._name = f"{self.path.replace('.py', '')}.{self.func_name}"

        self._id = f"cmp{self._index}@" + self._name

        for key, value in self.index_scope.items():
            self.index_scope[key] = PathIndexRange(value)

    def validate(self, cfg):
        """
        Validate the object
        """
        # Check for circular refs
        consumes_results = set(binding.path for binding in self.consumes_results)
        circ_refs = consumes_results.intersection(
            binding.path for binding in self.provides_results
        )
        assert (
            len(circ_refs) == 0
        ), f"Component at index {self._index} has circular reference(s): {', '.join(circ_refs)}"

        # Check if consumes_results and consumes_input have same names
        consumes_results_names = set(binding.name for binding in self.consumes_results)
        consumes_input_names = set(binding.name for binding in self.consumes_input)
        names_reused = consumes_results_names.intersection(consumes_input_names)
        assert (
            len(names_reused) == 0
        ), f"Component at index {self._index} has names: '{', '.join(names_reused)}' in both 'consumes_results' and 'consumes_input'"

        assert len(self.index_scope) < 2, "Maximum one index scope allowed"

        self._validate_scope()
        return self

    def _validate_scope(self):
        """
        Check for index ranges that are not a subset of the index scope

        Raises HubitModelComponentError if not successful
        """
        paths_provided = [binding.path for binding in self.provides_results]
        cmp_scope_idxid, cmp_scope = self.scope_range
        if cmp_scope_idxid is not None:
            for path in paths_provided:
                path_range = path.range_for_identifiers()[cmp_scope_idxid]
                if not cmp_scope.includes(path_range):
                    raise HubitModelComponentError(
                        (
                            f"Path range '{path_range}' in path '{path}' "
                            f"not included in component index scope '{self.index_scope}' "
                            f"for component '{self.id}'."
                        )
                    )

    @property
    def scope_range(self) -> Union[Tuple[str, PathIndexRange], Tuple[None, None]]:
        if len(self.index_scope) > 0:
            idx_spec = list(self.index_scope.keys())[0]
            return idx_spec, self.index_scope[idx_spec]
        else:
            return None, None

    @property
    def scope_start(self) -> Union[Tuple[str, int], Tuple[None, None]]:
        scope_idx_spec, scope_range = self.scope_range
        if scope_range is not None:
            scope_start = scope_range.start
            # For components scopes the pathIndexRange cannot
            # be empty but mypy cannot know this
            scope_start = cast(int, scope_start)
            scope_idx_spec = cast(str, scope_idx_spec)
            return scope_idx_spec, scope_start
        else:
            return None, None

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @classmethod
    def from_cfg(cls, cfg: Dict, idx: int) -> HubitModelComponent:
        """
        Create instance from configuration data

        Args:
            cfg (Dict): Configuration

        Returns:
            HubitModelComponent: Object corresponsing to the configuration data
        """
        _cfg = copy.deepcopy(cfg)
        target_attr = "provides_results"
        try:
            _cfg[target_attr] = [
                HubitBinding.from_cfg(binding) for binding in _cfg[target_attr]
            ]
        except KeyError:
            raise HubitModelComponentError(
                f'Component with entrypoint "{_cfg["func_name"]}" should provide results'
            )

        target_attr = "consumes_input"
        try:
            _cfg[target_attr] = [
                HubitBinding.from_cfg(binding) for binding in _cfg[target_attr]
            ]
        except KeyError:
            pass

        target_attr = "consumes_results"
        try:
            _cfg[target_attr] = [
                HubitBinding.from_cfg(binding) for binding in _cfg[target_attr]
            ]
        except KeyError:
            pass

        _cfg["_index"] = idx

        return cls(**_cfg).validate(_cfg)

    def does_provide_results(self):
        return len(self.provides_results) > 0

    def does_consume_results(self):
        return len(self.consumes_results) > 0

    def does_consume_input(self):
        return len(self.consumes_input) > 0

    def binding_map(self, binding_type):
        bindings = getattr(self, binding_type)
        return {binding.name: binding.path for binding in bindings}

    def query_depths(self):
        return [binding.path.as_query_depth_path() for binding in self.consumes_input]

    def include_patterns(self):
        return [binding.path.as_include_pattern() for binding in self.consumes_input]

    @property
    def provides_results_paths(self) -> List[HubitModelPath]:
        return [binding.path for binding in self.provides_results]

    @property
    def consumes_input_paths(self) -> List[HubitModelPath]:
        return [binding.path for binding in self.consumes_input]

    @property
    def consumes_results_paths(self) -> List[HubitModelPath]:
        return [binding.path for binding in self.consumes_results]


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

        self._component_for_id = {
            component.id: component for component in self.components
        }

        self._query_depths = [
            query_depth
            for component in self.components
            for query_depth in component.query_depths()
        ]

        self.include_patterns = [
            include_pattern
            for component in self.components
            for include_pattern in component.include_patterns()
        ]

        # Compile query depths
        self.compiled_query_depths = [
            query_depth.compile_regex() for query_depth in self._query_depths
        ]

    @property
    def base_path(self):
        return self._base_path

    @property
    def component_for_id(self):
        return self._component_for_id

    def validate(self):
        """
        Validate the object
        """
        # Check that there are not multiple components that provide the same data
        paths = [
            binding.path.set_range_for_idxid(component.index_scope)
            for component in self.components
            for binding in component.provides_results
        ]
        duplicates = [item for item, count in Counter(paths).items() if count > 1]
        if len(duplicates) > 0:
            msg = (
                f"Fatal error. Multiple providers for model paths:"
                f"{set(duplicates)}. Paths provided in the model "
                f"files may be unintentionally identical or missing "
                f" a unique scopes."
            )
            raise HubitError(msg)
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
        # Read, instantiate and validate components
        components = [
            HubitModelComponent.from_cfg(component_data, idx)
            for idx, component_data in enumerate(cfg["components"])
        ]

        return cls(components=components, _base_path=base_path).validate()

    def provides(self) -> Tuple[List[str], List[HubitModelPath]]:
        """Returns two lists with
        1) component ID
        2) Binding path for attributes provided with scope set
        """
        cmp_ids, paths_provided, scopes = zip(
            *[
                (cmp.id, binding.path, cmp.index_scope)
                for cmp in self.components
                for binding in cmp.provides_results
            ]
        )

        # Set the scope to check if provided paths are unique
        paths_provided = [
            path.set_range_for_idxid(scope)
            for path, scope in zip(paths_provided, scopes)
        ]

        return cmp_ids, paths_provided


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

    _path_cls = HubitQueryPath

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
        items: Dict[Any, Any] = dict()
        for k, v in self.items():
            # path components are strings
            _k = _HubitPath.as_internal(k)
            keys = _k.split(SEP)
            sub_items = items
            for ki in keys[:-1]:
                _ki = int(ki) if is_digit(ki) else ki
                try:
                    sub_items = sub_items[_ki]
                except KeyError:
                    sub_items[_ki] = dict()
                    sub_items = sub_items[_ki]

            sub_items[keys[-1]] = v

        return items

    @staticmethod
    def _match(path: str, stop_at: List):
        """
        Check if path matches any of the compiled regex in the
        stop_at list
        """
        if any(prog.search(path) for prog in stop_at):
            return True
        else:
            return False

    @staticmethod
    def _include(path: str, include_patterns: List[str]):
        """
        Check if the path is in the list of patterns to be included
        """
        # Replace .DIGITS with empty string
        _path = re.sub(r"\.\d+", "", path)
        return any(include.startswith(_path) for include in include_patterns)

    @classmethod
    def from_dict(
        cls,
        dict: Dict,
        parent_key: str = "",
        sep: str = ".",
        stop_at: List = [],
        include_patterns=[],
        as_dotted: bool = False,
    ):
        """
        Flattens dict and concatenates keys to a dotted style internal path
        """
        items = []
        for k, v in dict.items():
            new_key = parent_key + sep + k if parent_key else k
            if FlatData._match(new_key, stop_at):
                items.append((cls._path_cls(new_key), v))
                continue

            if not FlatData._include(new_key, include_patterns):
                continue

            if isinstance(v, Dict):
                items.extend(
                    cls.from_dict(
                        v,
                        new_key,
                        sep=sep,
                        stop_at=stop_at,
                        include_patterns=include_patterns,
                    ).items()
                )
            elif isinstance(v, abc.Iterable) and not isinstance(v, str):
                try:  # Elements are dicts
                    # Test with element 0 - if there is a match then treat all elements accordingly
                    if FlatData._match(new_key + ".0", stop_at):
                        for idx, item in enumerate(v):
                            _new_key = new_key + "." + str(idx)
                            items.append((cls._path_cls(_new_key), item))
                    else:
                        for idx, item in enumerate(v):
                            _new_key = new_key + "." + str(idx)
                            items.extend(
                                cls.from_dict(
                                    item,
                                    _new_key,
                                    sep=sep,
                                    stop_at=stop_at,
                                    include_patterns=include_patterns,
                                ).items()
                            )
                except AttributeError:
                    # Elements are not dicts
                    # Keep list with not flattening
                    # items.append((HubitModelPath(new_key), v))
                    # Flatten simple list
                    for idx, item in enumerate(v):
                        _new_key = new_key + "." + str(idx)
                        items.append((cls._path_cls(_new_key), item))
            else:
                items.append((cls._path_cls(new_key), v))
        if as_dotted:
            return cls(items)
        else:
            return cls([(cls._path_cls.from_dotted(key), val) for key, val in items])

    @classmethod
    def from_flat_dict(cls, dict: Dict):
        """
        Create object from a regular flat dictionary
        """
        return cls({cls._path_cls(k): v for k, v in dict.items()})

    def as_dict(self) -> Dict[str, Any]:
        """
        Converts the object to a regular dictionary with string keys
        """
        return {str(k): v for k, v in self.items()}

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
            yaml.safe_dump(self.as_dict(), handle)
