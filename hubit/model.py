"""
This module contains the `HubitModel` class which is used 
for executing your calculations.
"""

# TODO: skipfun
# return value from get_many

from __future__ import annotations
import pathlib
import datetime
import hashlib
import pickle
from dataclasses import dataclass, field, fields
from typing import (
    Any,
    List,
    Sequence,
    Tuple,
    Dict,
    Optional,
    TYPE_CHECKING,
)
import logging
import os
import time
import copy
import itertools
from multiprocessing import Pool
import warnings

from .qrun import query_runner_factory
from .tree import LengthTree, _QueryExpansion, tree_for_idxcontext
from .config import FlatData, HubitModelConfig, Query, PathIndexRange, HubitQueryPath
from .render import get_dot

from .errors import (
    HubitError,
    HubitModelNoInputError,
    HubitModelNoResultsError,
    HubitModelValidationError,
    HubitModelQueryError,
)

if TYPE_CHECKING:
    from .config import HubitBinding, HubitModelComponent, HubitModelPath
    from .qrun import _QueryRunner

_CACHE_DIR = ".hubit_cache"
_HUBIT_DIR = os.path.dirname(os.path.realpath(__file__))
_CACHE_DIR = os.path.join(_HUBIT_DIR, _CACHE_DIR)
IDX_WILDCARD = PathIndexRange.wildcard_chr


def _default_skipfun(flat_input: FlatData) -> bool:
    """
    flat_input is the input for one factor combination in a sweep
    calculation
    """
    return False


def _get(
    queryrunner: _QueryRunner,
    query: Query,
    flat_input,
    flat_results: Optional[FlatData] = None,
    dryrun: bool = False,
):
    """
    With the 'queryrunner' object deploy the paths
    in 'query'.

    flat_results is a dict and will be modified

    If dryrun=True the workers will generate dummy results. Usefull
    to validate s query.
    """

    queries_exp, err, status = queryrunner.run(query, flat_input, flat_results, dryrun)

    if err is None:
        # TODO: compression call belongs on model (like expand)
        response = queryrunner.model._collect_results(
            queryrunner.flat_results, queries_exp
        )

        return response, queryrunner.flat_results
    else:
        print("Exited with runner status")
        print(status)
        # Re-raise if failed
        raise err


class HubitModel:
    _valid_model_caching_modes = "none", "incremental", "after_execution"
    _do_model_caching = "incremental", "after_execution"

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

        self.model_cfg = model_cfg

        # Stores length tree. Filled when set_input() is called
        self.tree_for_idxcontext: Dict[str, LengthTree] = {}

        # Stores normalized query paths
        self._normqpath_for_qpath: Dict[str, str] = {}

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
        self.flat_input = FlatData.from_dict(
            input_data,
            stop_at=self.model_cfg.compiled_query_depths,
            include_patterns=self.model_cfg.include_patterns,
        )
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

        dot, filename = get_dot(self, _query, file_idstr)
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
        warnings.warn(
            "The method 'get_results' on 'HubitModel' is deprecated. Use the 'results' property instead.",
            DeprecationWarning,
        )
        return self.flat_results

    @property
    def results(self) -> FlatData:
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

        # Create a query runner
        self._qrunner = query_runner_factory(
            use_multi_processing, self, self._component_caching
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
                _flat_input[path] = val

            if skipfun(_flat_input):
                continue
            # Never use multiprocessing in the worker pool
            qrun = query_runner_factory(
                False, self, component_caching=self._component_caching
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

    def clean_log(self):
        self._log._clean()

    @property
    def base_path(self):
        return self.model_cfg.base_path

    def _add_log_items(
        self,
        worker_counts: Dict[str, int],
        elapsed_time: float,
        cache_counts: Dict[str, int],
    ):
        self._log._add_items(worker_counts, elapsed_time, cache_counts)

    def _get_id(self):
        """
        ID of the model based on configuration and input

        TODO: We could easily include the entry point function which includes the version
        https://stackoverflow.com/questions/3431825/generating-an-md5-checksum-of-a-file
        """
        return hashlib.md5(
            pickle.dumps({"input": self.inputdata, "cfg": self.model_cfg})
        ).hexdigest()

    def _get_binding_ids(self, prefix_input, prefix_results):
        """
        Get list of objects from model that need redering e.g. layers and segment.
        These object name are prefixed to cluster them
        """
        results_object_ids = set()
        input_object_ids = set()
        for component in self.model_cfg.components:
            bindings = component.provides_results
            results_object_ids.update(
                [
                    "{}_{}".format(prefix_results, objname)
                    for objname in self._get_path_cmps(bindings)
                ]
            )

            bindings = component.consumes_input
            input_object_ids.update(
                [
                    "{}_{}".format(prefix_input, objname)
                    for objname in self._get_path_cmps(bindings)
                ]
            )

            bindings = component.consumes_results
            results_object_ids.update(
                [
                    "{}_{}".format(prefix_results, objname)
                    for objname in self._get_path_cmps(bindings)
                ]
            )

        results_object_ids = list(results_object_ids)
        input_object_ids = list(input_object_ids)
        return input_object_ids, results_object_ids

    def _get_path_cmps(self, bindings: Sequence[HubitBinding]):
        """
        Get path components from bindings
        """
        cmps = set()
        for binding in bindings:
            pathcmps = binding.path.remove_braces().split(".")
            if len(pathcmps) - 1 > 0:
                cmps.update(pathcmps[:-1])
        return cmps

    def _set_trees(self):
        """Compute and set trees for all index contexts in model"""
        self.tree_for_idxcontext = tree_for_idxcontext(
            self.model_cfg.component_for_id.values(), self.inputdata
        )

    def _validate_query(self, query: Query, use_multi_processing: bool = False):
        """
        Run the query using a dummy calculation to see that all required
        input and results are available
        """
        qrunner = query_runner_factory(use_multi_processing, self)
        _get(qrunner, query, self.flat_input, dryrun=True)
        return qrunner.workers

    def _validate_model(self):
        fname_for_path = {}
        for component in self.model_cfg.components:
            fname = component.func_name
            for binding in component.provides_results:
                if not binding.path in fname_for_path:
                    fname_for_path[binding.path] = fname
                else:
                    raise HubitModelValidationError(binding.path, fname, fname_for_path)

    def _cmpids_for_query(
        self, qpath: HubitQueryPath, check_intersection: bool = True
    ) -> List[str]:
        """
        Find IDs of components that can respond to the "query".
        """
        # TODO: Next line should only be executed once in init (speed)
        cmp_ids, paths_provided = self.model_cfg.provides()

        return [
            cmp_ids[idx]
            for idx in qpath.idxs_for_matches(paths_provided, check_intersection)
        ]

    def component_for_id(self, compid: str) -> HubitModelComponent:
        return self.model_cfg.component_for_id[compid]

    def _cmpid_for_query(self, path: HubitQueryPath) -> str:
        """Find ID of component that can respond to the "query".

        Args:
            path: Query path

        Raises:
            HubitModelQueryError: Raised if no or multiple components provide the
            queried attribute

        Returns:
            str: Function name
        """
        # Get all components that provide data for the query
        cmp_ids = self._cmpids_for_query(path)

        if len(cmp_ids) > 1:
            msg = f"Fatal error. Multiple providers for query path '{path}': {cmp_ids}. Note that query path might originate from an expansion of the original query."
            raise HubitModelQueryError(msg)

        if len(cmp_ids) == 0:
            msg = f"Fatal error. No provider for query path '{path}'."
            raise HubitModelQueryError(msg)
        return cmp_ids[0]

    def component_for_qpath(self, path: HubitQueryPath) -> HubitModelComponent:
        return self.component_for_id(self._cmpid_for_query(path))

    def mpaths_for_qpath_fields_only(
        self, qpath: HubitQueryPath
    ) -> Tuple[List[HubitModelPath], List[str]]:
        """Find model paths that match the query. The match
        is evaluated only based on field names
        """
        check_intersection = False

        # Find component that provides queried result
        cmp_ids = self._cmpids_for_query(qpath, check_intersection=check_intersection)

        # Find component
        mpaths = []
        for cmp_id in cmp_ids:
            # Get the provided paths
            binding_paths = self.model_cfg.component_for_id[
                cmp_id
            ].provides_results_paths
            # Find index in list of binding paths that match query path (there can
            # be only one match which should be validated elsewhere)
            idx = qpath.idxs_for_matches(
                binding_paths, check_intersection=check_intersection
            )[0]
            mpaths.append(binding_paths[idx])
        return mpaths, cmp_ids

    def _expand_query(
        self, qpath: HubitQueryPath, store: bool = True
    ) -> _QueryExpansion:
        """
        Expand query so that any index wildcards are converted to
        real indies

        qpath: The query path to be expanded. Both braced and dotted paths are accepted.
        store: If True some intermediate results will be saved on the
            instance for later use.

        TODO: Save pruned trees so the worker need not prune top level trees again
        TODO: save component so we dont have to find top level components again
        """

        # Find mpaths and component IDs
        mpaths, cmp_ids = self.mpaths_for_qpath_fields_only(qpath)

        # Find components corresponding to the IDs
        cmps = [self.model_cfg.component_for_id[cmp_id] for cmp_id in cmp_ids]

        # Get the tree that corresponds to the (one) index context
        index_context = _QueryExpansion.get_index_context(qpath, mpaths)
        tree = self.tree_for_idxcontext[index_context]

        # Create and return expansion object
        return _QueryExpansion(qpath, mpaths, tree, cmps)

    def _collect_results(
        self, flat_results: FlatData, query_expansions: List[_QueryExpansion]
    ):
        """
        Compress the response to reflect queries with index wildcards.
        So if the query has the structure list1[:].list2[:] and is
        rectangular with 2 elements in list1 and 3 elements
        in list2 the compressed response will be a nested list like
        [[00, 01, 02], [10, 11, 12]]
        """
        return {
            qexp.path: qexp.collect_results(flat_results) for qexp in query_expansions
        }


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

    def _clean(self):
        self.log_items = []

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
