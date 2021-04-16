"""
This module contains the `hubit` HubitModel class which is used 
for executing your calculations.
"""

# TODO: Dataclass for response and flat results 
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
import yaml
from multiprocessing import Pool

from .qrun import _QueryRunner
from ._model import _HubitModel, _get, default_skipfun
from .shared import (
    LengthTree,
    flatten,
    inflate,
)
from .config import HubitModelConfig, HubitModelPath, HubitQueryPath

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
        base_path: str = "cwd",
        output_path: str = "./",
        name: str = "NA",
    ):
        """Initialize a Hubit model. Consider initializing a model using 
        [`from_file`][hubit.model.HubitModel.from_file] method instead.

        Args:
            model_cfg: Model configuration
            base_path: Base path for the model
            output_path: Output path relative to base_path
            name: Model name

        Raises:
            HubitError: If `output_path` is an absolute path or if components function names are not unique.
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
        self.base_path = os.getcwd() if base_path == "cwd" else base_path
        self.odir = os.path.normpath(os.path.join(self.base_path, output_path))
        self.inputdata: Dict[str, Any] = {}
        self.flat_input: Dict[str, Any] = {}
        self.flat_results: Dict[str, Any] = {}
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
            model_file_path: The location of the model file. The model `base_path` will 
                be set to the path of the model file and consequently the 
                [`HubitModelComponent`][hubit.config.HubitModelComponent] 
                `path` attribute should be relative to the model file
            output_path: Path where results should be saved
            name: Model name

        Returns:
            Hubit model object as defined in the specified model file
        """
        model_config = HubitModelConfig.from_file(model_file_path)
        base_path = model_config.base_path

        return cls(
            model_config, name=name, output_path=output_path, base_path=base_path
        )

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
        Set the caching on/off for workers.

        Arguments:
            component_caching (bool): True corresponds to worker caching in on.
        """
        self._component_caching = component_caching

    def set_model_caching(self, caching_mode: str):
        """
        Set the model caching mode.

        Arguments:
            caching_mode: Valid options are: "none", "incremental", "after_execution". 
                If "none" model results are not cached. If "incremental" the results are 
                saved to disk whenever a component worker finishes its workload. If 
                "after_execution" the results are saved to disk when all component 
                workers have finished their workload 
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
            input_data: Input data.

        Returns:
            Hubit model with input set.
        """
        self.inputdata = input_data
        self.flat_input = flatten(input_data)
        self._set_trees()
        self._input_is_set = True
        return self

    def set_results(self, results_data: Dict[str, Any]) -> HubitModel:
        """
        Set the (hierarchical) results on the model.

        Args:
            results_data: Results data.

        Returns:
            Hubit model with input set
        """
        self.flat_results = flatten(results_data)
        self.flat_results = {HubitModelPath(k): v for k, v in self.flat_results.items()}
        return self

    def render(self, query: List[str] = [], file_idstr: str = "") -> None:
        """Renders graph representing the model or the query.

        Args:
            query: Sequence of strings that each complies with 
                a [`HubitQueryPath`][hubit.config.HubitQueryPath]. If not provided 
                (or is empty) the model is rendered. If a non-empty `query` is 
                provided that query is rendered, which requires the input data 
                be set.
            file_idstr: Identifier appended to the image file name.
        """

        dot, filename = self._get_dot(query, file_idstr)
        filepath = os.path.join(self.odir, filename)
        dot.render(filepath, view=False)
        if os.path.exists(filepath):
            os.remove(filepath)

    def get_results(self, flat: bool = False) -> Dict[str, Any]:
        """
        Get model results

        Args:
            flat: If `True` the results will be returned as a 
                flat dict. Otherwise the returned results is a nested 
                dict.

        Returns:
            Results
        """
        if flat:
            return self.flat_results
        else:
            return inflate(self.flat_results)

    def get(
        self,
        query: List[str],
        use_multi_processing: bool = False,
        validate: bool = False,
        use_results: str = "none",
    ) -> Dict[str, Any]:
        """Get the respose corresponding to the `query`

        On Windows calling `get` should be guarded by
        if `__name__ == '__main__':` if `use_multi_processing = True`


        Args:
            query: Sequence of strings that each complies with a [`HubitQueryPath`][hubit.config.HubitQueryPath].
            use_multi_processing: Flag indicating if the respose should be generated using (async) multiprocessing.
            validate: Flag indicating if the query should be validated prior to execution. If `True` a dry-run of the model will be executed. 
            use_results. Should previously saved results be used. 
                If 'current' the results set on the model will be used 
                as-is i.e. not recalculated. If 'cached' internally saved results 
                will be used if they exists. Defaults to "none" i.e no cached results 
                will be used.

        Raises:
            HubitModelNoInputError: If no input is set on the model

        Returns:
            The response
        """
        if not self._input_is_set:
            raise HubitModelNoInputError()

        if use_results == "current" and self.flat_results is None:
            raise HubitModelNoResultsError()

        _ = [HubitQueryPath(path).validate() for path in query]

        # Make a query runner
        self._qrunner = _QueryRunner(
            self, use_multi_processing, self._component_caching
        )

        if validate:
            _get(self._qrunner, query, self.flat_input, dryrun=True)

        if use_results == "current":
            logging.info("Using current model results.")
            _flat_results = self.flat_results
        elif use_results == "cached":
            if self.has_cached_results():
                logging.info("Using cached results.")
                with open(self._cache_file_path, "r") as stream:
                    _flat_results = yaml.load(stream, Loader=yaml.FullLoader)
                    _flat_results = {HubitModelPath(k): v for k, v in _flat_results.items()}
            else:
                logging.info("No cached results found.")
                _flat_results = {}
        elif use_results == "none":
            logging.info("No results used.")
            _flat_results = {}
        else:
            raise HubitError(
                f"Unknown value '{use_results}' for argument 'use_results'"
            )

        response, self.flat_results = _get(
            self._qrunner, query, self.flat_input, _flat_results
        )
        return response

    def get_many(
        self,
        query: List[str],
        input_values_for_path: Dict[str, Any],
        skipfun: Callable[[Dict[str, Any]], bool] = default_skipfun,
        nproc: Any = None,
    ) -> Tuple:
        """Perform a full factorial sampling of the
        input points specified in `input_values_for_path`.

        On Windows calling `get_many` should be guarded by
        if `__name__ == '__main__':`

        Args:
            query: Sequence of strings that each complies with a [`HubitQueryPath`][hubit.config.HubitQueryPath].
            input_values_for_path: Dictionary with keys representing path items. The corresponding values should be an iterable with elements representing discrete values for the attribute at the path.
            skipfun: If returns True the factor combination is skipped
            nproc: Number of processes to use. If `None` a suitable default is used.

        Raises:
            HubitModelNoInputError: [description]

        Returns:
            3-tuple with a list of responses in the element 0, a list of the
            corresponding inputs in element 1 and a list of the results in element 2.
        """
        if not self._input_is_set:
            raise HubitModelNoInputError()

        _ = [HubitQueryPath(path).validate() for path in query]

        tstart = time.time()

        # Get paths to change in paths and the values each path should assume in pvalues
        paths, pvalues = zip(*input_values_for_path.items())

        # List of tuples each containing values for each path in paths
        ppvalues = list(itertools.product(*pvalues))

        args = []
        inps = []
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
            flat_results: Dict[str, Any] = {}
            args.append((qrun, query, _flat_input, flat_results))
            inps.append(_flat_input)

        if len(args) == 0:
            raise HubitError("No args found for sweep")

        if nproc is None:
            _nproc = len(args)
        else:
            _nproc = max(nproc, 1)
        with Pool(_nproc) as pool:
            results = pool.starmap(_get, args)
            responses, flat_results = zip(*results)
            results = [inflate(item) for item in flat_results]

        logging.info("Query processed in {} s".format(time.time() - tstart))

        # TODO convert inps to external paths
        return responses, inps, results

    def validate(self, query: List[str] = []) -> bool:
        """
        Validate a model or query. Will validate as a query if
        query are provided.

        Args:
            query: Query paths. 

        Raises:
            HubitModelNoInputError: If not input is set.
            HubitModelValidationError: If validation fails.

        Returns:
            True if validation was successful.
        """
        # TODO: check for circular references,
        #       Component that consumes a specified index ID should also provide a result at the same location in the results data model. Not necesary if all indices (:) are consumed. I.e. the provider path should contain all index info
        if len(query) > 0:
            if not self._input_is_set:
                raise HubitModelNoInputError()
            self._validate_query(query, use_multi_processing=False)
        else:
            self._validate_model()

        return True

    def log(self) -> HubitLog:
        """
        Get the model log

        Returns:
            Model log object
        """
        return self._log


def now():
    return datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")


@dataclass
class LogItem:
    """
    Hubit log item. Keys in all attribute dicts (e.g.
    worker_counts and cache_counts) are the same.

    Args:
        elapsed_time (float): Query execution time
        worker_counts (Dict[str, int]): For each component function name the value is the count of spawned workers.
        cache_counts (Dict[str, int]): For each component function name the value is the count of workers that used the component cache.
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
    _header_fstr = " ".join(["{:<20}", "{:^12}", "{:^25}", "{:^15}", "{:^20}"])
    _value_fstr = " ".join(["{:<20}", "{:^12.2}", "{:^25}", "{:^15}", "{:^20}"])
    _n_columns = len(_order) + len(_extra_col)

    @classmethod
    def get_table_header(cls) -> str:
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

        return cls._header_fstr.format(*headers)

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
        for vals in vals_for_row_idx:
            lines.append(self._value_fstr.format(*vals))

        # print(lines)
        return "\n".join(lines)


@dataclass
class HubitLog:
    """
    Hubit log. The log collects various run data such as the number of 
    workers spawned and the executions time. 

    Args:
        log_items (List[LogItem]): List of log items. Newest item is
            stored as the the first element.
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
        """Get all log item values corresponding to attribute name "attr"

        Args:
            attr (str): Available attributes are attributes names of the 
                [LogItem][hubit.model.LogItem] class.

        Returns:
            List: Log item values
        """
        try:
            return [getattr(item, attr) for item in self.log_items]
        except AttributeError:
            raise AttributeError(
                f"Available attributes are: {', '.join([f.name for f in fields(LogItem)])}"
            )

    def __str__(self):
        sepstr = "-"
        lines = [LogItem.get_table_header()]
        for logitem in self.log_items:
            lines.append(str(logitem))
        width = max([len(line.split("\n")[0]) for line in lines])
        sep = width * sepstr
        lines.insert(1, sep)
        lines.insert(0, sep)
        lines.append(sep)
        return "\n".join(lines)
