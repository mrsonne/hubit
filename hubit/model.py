"""
This module contains the `HubitModel` class which is used 
for executing your calculations.
"""

# TODO: skipfun
# return value from get_many

from __future__ import annotations
import pathlib
import datetime
from dataclasses import dataclass, field, fields
from typing import Any, Callable, List, Tuple, Dict
import logging
import os
import time
import copy
import itertools
from multiprocessing import Pool

from .qrun import _QueryRunner
from ._model import _HubitModel, _get, _default_skipfun
from .shared import LengthTree
from .config import FlatData, HubitModelConfig, HubitModelPath, Query

from .errors import (
    HubitError,
    HubitModelNoInputError,
    HubitModelNoResultsError,
)

_CACHE_DIR = ".hubit_cache"
_HUBIT_DIR = os.path.dirname(os.path.realpath(__file__))
_CACHE_DIR = os.path.join(_HUBIT_DIR, _CACHE_DIR)


class HubitModel(_HubitModel):
    def __init__(
        self,
        model_cfg: HubitModelConfig,
        output_path: str = "./",
        name: str = "NA",
    ):
        """Initialize a Hubit model. Consider initializing a model using
        [`from_file`][hubit.model.HubitModel.from_file] method instead.

        Args:
            model_cfg: Model configuration object
                [`HubitModelConfig`][hubit.config.HubitModelConfig]
            output_path: Output path relative to the base_path on the
            `HubitModelConfig` instance.
            name: Model name.

        Raises:
            HubitError: If `output_path` is an absolute path.
        """

        if os.path.isabs(output_path):
            raise HubitError("Output path should be relative")

        # TODO: NOT USED
        self.ilocstr = "_IDX"
        self.model_cfg = model_cfg

        # Stores length tree. Filled when set_input() is called
        self.tree_for_idxcontext: Dict[LengthTree, str] = {}

        # Stores trees for query
        self._tree_for_qpath: Dict[LengthTree, str] = {}

        # Stores normalized query paths
        self._normqpath_for_qpath: Dict[str, str] = {}

        # Store the model path that matches the query
        self._modelpath_for_querypath: Dict[str, str] = {}

        self.name = name
        self.odir = os.path.normpath(os.path.join(model_cfg.base_path, output_path))
        self.inputdata: Dict[str, Any] = {}
        self.flat_input = FlatData()
        self.flat_results = FlatData()
        self._input_is_set = False

        # Set the query runner. Saving it on the instance is used for testing
        self._qrunner: Any = None

        self._component_caching = False
        self._model_caching_mode = "none"
        self._cache_dir = _CACHE_DIR
        self._cache_file_path = os.path.join(self._cache_dir, f"{self._get_id()}.yml")

        self._log = HubitLog()

    @classmethod
    def from_file(
        cls, model_file_path: str, output_path: str = "./", name: str = "NA"
    ) -> HubitModel:
        """Creates a `HubitModel` from a configuration file.

        Args:
            model_file_path: The location of the model file.
            output_path: Path where results should be saved
            name: Model name

        Returns:
            Hubit model object as defined in the specified model file
        """
        model_config = HubitModelConfig.from_file(model_file_path)
        base_path = model_config.base_path

        return cls(model_config, name=name, output_path=output_path)

    def has_cached_results(self) -> bool:
        """
        Check if the model has cached results

        Returns:
            The result of the check
        """
        return os.path.exists(self._cache_file_path)

    def clear_cache(self):
        """
        Clear the model cache. Will delete the serialized model cache
        from the disk if it exists.
        """
        if self.has_cached_results():
            os.remove(self._cache_file_path)

    def set_component_caching(self, component_caching: bool):
        """
        Set component worker caching on/off.

        Arguments:
            component_caching (bool): True corresponds to worker caching being on.
        """
        self._component_caching = component_caching

    def set_model_caching(self, caching_mode: str):
        """
        Set the model caching mode.

        Arguments:
            caching_mode: Valid options are: "none", "incremental", "after_execution".
                If "none" model results are not cached. If "incremental" results are
                saved to disk whenever a component worker finishes its workload. If
                the `caching_mode` is set to "after_execution" the results are saved
                to disk when all component workers have finished their workloads.

        Results caching is useful when you want to avoid spending time calculating
        the same results multiple times. A use case for "incremental" caching is when
        a calculation is stopped (computer shutdown, keyboard interrupt,
        exception raised) before the response has been generated. In such cases
        the calculation can be restarted from the cached results. The overhead
        introduced by caching makes it especially useful for CPU bound models.
        A use case for "after_execution" caching is when writing the result data
        incrementally is a bottleneck.

        __Warning__. Cached results are tied to the content of the model configuration
        file and the model input. `Hubit` does not check if any of the underlying calculation
        code has changed. Therefore, using results caching while components
        are in development is not recommended.

        `Hubit`'s behavior in four parameter combinations is summarized below.
        "Yes" in the Write column corresponds to setting the caching level to either
        "incremental" or "after_execution" using the `set_model_caching` method.
        "No" in the Write column corresponds to caching level "none".
        "Yes" in the Read column corresponds
        `use_results="cached"` in the `get` method while "No" corresponds to
        `use_results="none"`.


        |Write  | Read  |  Behavior |
        |-------|-------|-----------|
        |Yes    | Yes   |  Any cached results for the model are loaded. These results will be saved (incrementally or after execution) and may be augmented in the new run depending on the new query |
        |Yes    | No    |  Model results are cached incrementally or after execution. These new results overwrite any existing results cached for the model |
        |No     | Yes   |  Any cached results for the model are loaded. No new results are cached and therefore the cached results will remain the same after execution.
        |No     | No    |  No results are cached and no results are loaded into the model |
        |       |       |           |

        """
        if not caching_mode in self._valid_model_caching_modes:
            raise HubitError(
                f"Unknown caching level '{caching_mode}'. Valid options are: {', '.join(self._valid_model_caching_modes)}"
            )

        self._model_caching_mode = caching_mode
        if self._model_caching_mode in self._do_model_caching:
            pathlib.Path(self._cache_dir).mkdir(parents=True, exist_ok=True)

    def set_input(self, input_data: Dict[str, Any]) -> HubitModel:
        """
        Set the (hierarchical) input on the model.

        Args:
            input_data: Input data as a freely formatted, serializable dictionary.

        Returns:
            Hubit model with input set.
        """
        self.inputdata = input_data
        self.flat_input = FlatData.from_dict(input_data)
        self._set_trees()
        self._input_is_set = True
        return self

    def set_results(self, results_data: Dict[str, Any]) -> HubitModel:
        """
        Set the (hierarchical) results on the model.

        Args:
            results_data: Results data as a freely formatted, serializable dictionary.

        Returns:
            Hubit model with input set
        """
        self.flat_results = FlatData.from_dict(results_data)
        return self

    def render(self, query: List[str] = [], file_idstr: str = ""):
        """Create graph representing the model or the query and save
        the image to the model `output_path`.

        Args:
            query: Sequence of strings that complies with
                [`Query`][hubit.config.Query]. If not provided
                (or is empty) the model is rendered. If a non-empty `query` is
                provided that query is rendered, which requires the input data
                be set.
            file_idstr: Identifier appended to the image file name.
        """
        _query = Query.from_paths(query)

        dot, filename = self._get_dot(_query, file_idstr)
        filepath = os.path.join(self.odir, filename)
        dot.render(filepath, view=False)
        if os.path.exists(filepath):
            os.remove(filepath)

    def get_results(self) -> FlatData:
        """
        Get model results as [`FlatData`][hubit.config.FlatData]

        Returns:
            Results for the model instance.
        """
        return self.flat_results

    def get(
        self,
        query: List[str],
        use_multi_processing: bool = False,
        validate: bool = False,
        use_results: str = "none",
    ) -> Dict[str, Any]:
        """Get the response corresponding to the `query`

        On Windows this method should be guarded by
        if `__name__ == '__main__':` if `use_multi_processing` is `True`


        Args:
            query: Sequence of strings that complies with [`Query`][hubit.config.Query].
            use_multi_processing: Flag indicating if the respose should be generated
                using (async) multiprocessing.
            validate: Flag indicating if the query should be validated prior
                to execution. If `True` a dry-run of the model will be executed.
            use_results: Should previously saved results be used.
                If `use_results` is set to "current" the results set on the model instance
                will be used as-is i.e. will not be recalculated.
                If `use_results` is set to "cached" cached results will be used
                if they exists. If `use_results` is set to "none" no previously
                calculated results will be used.

        Raises:
            HubitModelNoInputError: If no input is set on the model.
            HubitModelNoResultsError: If `use_results` = "current" but
                no results are present on the model.
            HubitError: If the specified `use_results` option is not known.

        Returns:
            The response
        """
        if not self._input_is_set:
            raise HubitModelNoInputError()

        if use_results == "current" and self.flat_results is None:
            raise HubitModelNoResultsError()

        _query = Query.from_paths(query)

        # Make a query runner
        self._qrunner = _QueryRunner(
            self, use_multi_processing, self._component_caching
        )

        if validate:
            _get(self._qrunner, _query, self.flat_input, dryrun=True)

        if use_results == "current":
            logging.info("Using current model results.")
            _flat_results = FlatData(self.flat_results)
        elif use_results == "cached":
            if self.has_cached_results():
                logging.info("Using cached results.")
                _flat_results = FlatData.from_file(self._cache_file_path)
            else:
                logging.info("No cached results found.")
                _flat_results = FlatData()
        elif use_results == "none":
            logging.info("No results used.")
            _flat_results = FlatData()
        else:
            raise HubitError(
                f"Unknown value '{use_results}' for argument 'use_results'"
            )

        response, self.flat_results = _get(
            self._qrunner, _query, self.flat_input, _flat_results
        )
        return response

    def get_many(
        self,
        query: List[str],
        input_values_for_path: Dict[str, Any],
        skipfun: Any = None,  # Callable[[FlatData], bool] = _default_skipfun,
        nproc: Any = None,
    ) -> Tuple:
        """Perform a full factorial sampling of the
        input points specified in `input_values_for_path`.

        On Windows calling this method should be guarded by
        if `__name__ == '__main__':`

        Args:
            query: Sequence of strings that complies with [`Query`][hubit.config.Query].
            input_values_for_path: Dictionary with string keys that each complies with
                [`HubitQueryPath`][hubit.config.HubitQueryPath].
                The corresponding values should be an iterable with elements
                representing discrete values for the attribute at the path. For
                each factor combination an input data object
                ([`FlatData`][hubit.config.FlatData]) will be created
                and passed to `skipfun`.
            skipfun: Callable that takes the flattened input for each factor combination
                as the only argument. If the skip function returns `True` the
                factor combination represented by the input data object is skipped.
                The default `skipfun` corresponding to
                `skipfun=None` always returns `False`.
            nproc: Number of processes to use. If `None` a suitable default is used.

        Raises:
            HubitModelNoInputError: If not input is set.

        Returns:
            Tuple of lists (responses, flat_inputs, flat_results). flat_inputs
            and flat_results both have elements of type [`FlatData`][hubit.config.FlatData]
        """
        if not self._input_is_set:
            raise HubitModelNoInputError()

        _query = Query.from_paths(query)

        tstart = time.time()

        # Get paths to change in paths and the values each path should assume in pvalues
        paths, pvalues = zip(*input_values_for_path.items())

        # List of tuples each containing values for each path in paths
        ppvalues = list(itertools.product(*pvalues))

        skipfun = skipfun or _default_skipfun

        args = []
        flat_inputs = []
        for pvalues in ppvalues:
            _flat_input = copy.deepcopy(self.flat_input)
            for path, val in zip(paths, pvalues):
                _flat_input[HubitModelPath.as_internal(path)] = val

            if skipfun(_flat_input):
                continue
            qrun = _QueryRunner(
                self,
                use_multi_processing=False,
                component_caching=self._component_caching,
            )
            flat_results = FlatData()
            args.append((qrun, _query, _flat_input, flat_results))
            flat_inputs.append(_flat_input)

        if len(args) == 0:
            raise HubitError("No args found for sweep")

        if nproc is None:
            _nproc = len(args)
        else:
            _nproc = max(nproc, 1)
        with Pool(_nproc) as pool:
            results = pool.starmap(_get, args)
            responses, flat_results = zip(*results)

        logging.info("Query processed in {} s".format(time.time() - tstart))

        return responses, flat_inputs, flat_results

    def validate(self, query: List[str] = []) -> bool:
        """
        Validate a model or query. Will validate as a query if
        query are provided.

        Args:
            query: Sequence of strings that complies with [`Query`][hubit.config.Query].

        Raises:
            HubitModelNoInputError: If not input is set.
            HubitModelValidationError: If validation fails.

        Returns:
            True if validation was successful.
        """
        # TODO: check for circular references,
        #       Component that consumes a specified index ID should also
        # provide a result at the same location in the results data model.
        # Not necesary if all indices (:) are consumed. I.e. the provider
        # path should contain all index info

        _query = Query.from_paths(query)

        if len(_query.paths) > 0:
            if not self._input_is_set:
                raise HubitModelNoInputError()
            self._validate_query(_query, use_multi_processing=False)
        else:
            self._validate_model()

        return True

    def log(self) -> HubitLog:
        """
        Get the model log

        Returns:
            [HubitLog][hubit.model.HubitLog] object
        """
        return self._log


def now():
    return datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")


@dataclass
class LogItem:
    """
    Hubit log item. Keys in all attribute dicts (e.g.
    `worker_counts` and `cache_counts`) are the same.

    Args:
        elapsed_time (float): Query execution time
        worker_counts (Dict[str, int]): For each component function name
            the value is the count of spawned workers.
        cache_counts (Dict[str, int]): For each component function name
            the value is the number of workers that used the cache.
        cached results. The keys are function names.
    """

    elapsed_time: float
    worker_counts: Dict[str, int]
    cache_counts: Dict[str, int]
    created_time: str = field(default_factory=now)

    _order = [
        "created_time",
        "elapsed_time",
        "worker_counts",
        "cache_counts",
    ]
    _headers = {
        "created_time": "Query finish time",
        "worker_counts": "Workers spawned",
        "elapsed_time": "Query took (s)",
        "cache_counts": "Component cache hits",
    }

    # Extra column (dict key) inserted before dataclass field. Only for Dict attributes
    _extra_col = {"worker_counts": "Worker name"}

    # Both fields and extra columns
    _header_formats = ["{:<20}", "{:^14}", "DUMMY", "{:^15}", "{:^20}"]
    _value_formats = ["{:<20}", "{:^14.2}", "DUMMY", "{:^15}", "{:^20}"]
    _n_columns = len(_order) + len(_extra_col)

    @classmethod
    def _get_header_fstr(cls, width):
        _header_formats = cls._header_formats
        _header_formats[2] = f"{{:^{width}}}"
        return " ".join(_header_formats)

    @classmethod
    def _get_value_fstr(cls, width):
        _value_formats = cls._value_formats
        _value_formats[2] = f"{{:^{width}}}"
        return " ".join(_value_formats)

    @classmethod
    def get_table_header(cls, width: int = 30) -> str:
        headers = [
            LogItem._headers[field_name]
            if field_name in LogItem._headers
            else field_name.replace("_", " ").title()
            for field_name in cls._order
        ]

        # Insert extra columns
        added = 0
        for target_field, xtra_header in LogItem._extra_col.items():
            idx = LogItem._order.index(target_field) + added
            headers.insert(idx, xtra_header)
            added += 1

        header_fstr = cls._get_header_fstr(width)
        return header_fstr.format(*headers)

    def width(self, field_name):
        val = getattr(self, field_name)
        if isinstance(val, Dict):
            values = list(val.values())
            if field_name in self._extra_col:
                values += list(val.keys())
            return max([len(str(val)) for val in values])
        else:
            return len(str(val))

    def set_width(self, width):
        self._width = width

    def __str__(self) -> str:
        items_for_field_idx = {}
        # Initialize an empty template row
        vals_row0 = [""] * LogItem._n_columns
        # Loop over columns in first row and insert values in template row
        for field_idx, field_name in enumerate(self._order):
            val = getattr(self, field_name)
            # Dicts should be expanded into one line per key
            if isinstance(val, Dict):
                # Store the dict by its field index and in a sorted version
                items_for_field_idx[field_idx] = list(sorted(val.items()))
                # Get the number of rows (same for all dicts in the log)
                nrows = len(items_for_field_idx[field_idx])
                # Don't write any values since dicts are handle in a separate loop
                continue
            vals_row0[field_idx] = val

        # Each dict-item should be expanded into "nrows" rows
        vals_for_row_idx = [[""] * LogItem._n_columns for _ in range(nrows)]
        # Insert first row
        vals_for_row_idx[0] = vals_row0
        field_idx_offset = 0
        # Loop over dict items i.e. potentially multi-line items that were omitted previously
        for field_idx, items in items_for_field_idx.items():
            extra_col = LogItem._order[field_idx] in LogItem._extra_col
            # Loop over (sorted) rows
            for row_idx, row in enumerate(items):
                if extra_col:
                    # Insert extra column (dict key)
                    vals_for_row_idx[row_idx][field_idx + field_idx_offset] = row[0]
                    # Insert dict value
                    vals_for_row_idx[row_idx][field_idx + 1 + field_idx_offset] = row[1]
                else:
                    vals_for_row_idx[row_idx][field_idx + field_idx_offset] = row[1]

            if extra_col:
                # Offset field index due to extra column
                field_idx_offset += 1

        lines = []
        value_fstr = self._get_value_fstr(self._width)
        for vals in vals_for_row_idx:
            lines.append(value_fstr.format(*vals))

        # print(lines)
        return "\n".join(lines)


@dataclass
class HubitLog:
    """
    Hubit log. For each query, various run data such as the number of
    workers spawned and the executions time is added to the log as a
    [LogItem][hubit.model.LogItem] as the first element.

    Often your simply want to print the log for a `HubitModel` instance e.g.
    `print(hmodel.log())`.
    """

    log_items: List[LogItem] = field(default_factory=list)

    def _add_items(
        self,
        worker_counts: Dict[str, int],
        elapsed_time: float,
        cache_counts: Dict[str, int],
    ):
        """
        Add log items to all lists
        """
        self.log_items.insert(
            0,
            LogItem(
                worker_counts=worker_counts,
                elapsed_time=elapsed_time,
                cache_counts=cache_counts,
            ),
        )

    def get_all(self, attr: str) -> List:
        """Get all log item values corresponding to attribute name `attr`.

        Examples:
            To get the elapsed time for all queries on the `HubitModel` instance
            `hmodel` execute `hmodel.log().get_all("elapsed_time")`. If two queries
            has been executed on the model,  the return value
            is a list of times e.g. `[0.5028373999812175, 0.6225477000162937]`
            where the first element represent the elapsed time for for latest
            query.

        Args:
            attr: Valid values are attributes names of the
                [LogItem][hubit.model.LogItem] class.

        Returns:
            Log item values for `attr`
        """
        try:
            return [getattr(item, attr) for item in self.log_items]
        except AttributeError:
            raise AttributeError(
                f"Available attributes are: {', '.join([f.name for f in fields(LogItem)])}"
            )

    def __str__(self):
        sepstr = "-"
        lines = []
        width = max(logitem.width("worker_counts") for logitem in self.log_items)
        for logitem in self.log_items:
            logitem.set_width(width)
            lines.append(str(logitem))
        total_width = max([len(line.split("\n")[0]) for line in lines])
        sep = total_width * sepstr
        lines.insert(0, LogItem.get_table_header(width))
        lines.insert(1, sep)
        lines.insert(0, sep)
        lines.append(sep)
        return "\n".join(lines)
