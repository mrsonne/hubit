from __future__ import annotations
from pprint import pprint
from hubit.utils import is_digit
import os
import json
import hashlib
import logging
import multiprocessing
from multiprocessing.managers import SyncManager
from multiprocessing import Value
from ctypes import c_bool
import copy
from typing import Any, Callable, Dict, Set, TYPE_CHECKING, List, Optional, Union
from .config import FlatData, HubitBinding, HubitQueryPath, ModelIndexSpecifier
from .tree import LengthTree
from .utils import traverse, reshape, ReadOnlyDict
from operator import itemgetter

from .errors import HubitError, HubitWorkerError

if TYPE_CHECKING:
    from .config import HubitModelComponent


class _Worker:
    """ """

    RESULTS_FROM_CACHE_ID = "cache"
    RESULTS_FROM_CALCULATION_ID = "calculation"
    RESULTS_FROM_UNKNOWN = "unknown"

    def __init__(
        self,
        callback_ready: Callable,
        callback_completed: Callable,
        component: HubitModelComponent,
        query: HubitQueryPath,
        func: Callable,
        version: str,
        tree_for_idxcontext: Dict[str, LengthTree],
        manager: Optional[SyncManager] = None,
        dryrun: bool = False,
        caching: bool = False,
    ):
        """
        If inputdata is None the worker cannot work but can still
        render itself and print.

        query for one specific location ie no [:]
        query is an internal path (dot-path)

        """
        self.func = func  # function to excecute
        self.id = component.id  # name of the component
        self.name = component.name  # name of the component
        self.version = version  # Version of the component
        self._callback_ready = callback_ready
        self._callback_completed = callback_completed
        self.job = None  # For referencing the job if using multiprocessing
        self.query = query
        self.tree_for_idxcontext = tree_for_idxcontext
        self.component = component
        self._consumed_data_set = False
        self._consumed_input_ready = False
        self._consumed_results_ready = False
        self._consumes_input_only = False
        self._results_id: Optional[str] = None
        self.input_checksum: Optional[str] = None
        self.results_checksum: Optional[str] = None
        self.caching = caching
        self._did_start = False

        # Store information on how results were created (calculation or cache)
        self._results_from = self.RESULTS_FROM_UNKNOWN

        if dryrun:
            # If worker should perform a dry run set the worker function to "_work_dryrun"
            self.workfun = self._work_dryrun
        else:
            self.workfun = self._work

        # Paths for values that are consumed but not ready
        self.pending_input_paths: List[HubitQueryPath] = []
        self.pending_results_paths: List[HubitQueryPath] = []

        # Stores required values using internal names as keys
        self.inputval_for_name: Dict[str, Any] = {}
        self.resultval_for_name: Dict[str, Any] = {}

        # Stores required values using internal names as keys
        self.inputval_for_path: Dict[HubitQueryPath, Any] = {}
        self.resultval_for_path: Dict[HubitQueryPath, Any] = {}

        # Which indices are specified for each index ID
        self.idxval_for_idxid = {}

        # To store provided results. Values stores with the internal
        # name specified in the model as the key
        self.results: Dict[str, Any]
        if manager is None:
            self.results = {}
            self._did_complete = False
            self.use_multiprocessing = False
        else:
            self.results = manager.dict()
            self._did_complete = Value(c_bool, False)
            self.use_multiprocessing = True

        # TODO
        # 1) Prune tree corresponding to query
        # 2) Prune remaining trees based idxval_for_idxid (method does no exist yet on LengthTree)

        # Creating self.idxval_for_idxid from "provides_results" assumes that
        # the providers have all index identifiers from "consumes_input" and
        # "consumes_results" defined excluding the ones that have a range = ":".
        # This is reasonable since this assures that there is a well-defined place to
        # store the results.
        if self.component.does_provide_results():
            self.rpath_provided_for_name, self.idxval_for_idxid = _Worker.get_bindings(
                self.component.provides_results, query
            )
            self.provided_mpath_for_name = self.component.binding_map(
                "provides_results"
            )
        else:
            self.provided_mpath_for_name = None
            raise HubitWorkerError("No provider for Hubit model component '{self.id}'")

        # Model path for input dependencies with ilocs from query
        if self.component.does_consume_input():
            self.ipath_consumed_for_name = _Worker.bindings_from_idxs(
                self.component.consumes_input, self.idxval_for_idxid
            )
            # Allow model path lookup by internal name
            iconsumed_mpath_for_name = self.component.binding_map("consumes_input")
        else:
            self.ipath_consumed_for_name = {}
            iconsumed_mpath_for_name = {}

        # Model path for results dependencies with ilocs from query
        if self.component.does_consume_results():
            self._consumes_input_only = False
            self.rpath_consumed_for_name = _Worker.bindings_from_idxs(
                self.component.consumes_results, self.idxval_for_idxid
            )
            rconsumed_mpath_for_name = self.component.binding_map("consumes_results")
        else:
            self._consumes_input_only = True
            self.rpath_consumed_for_name = {}
            rconsumed_mpath_for_name = {}

        self._id = self.idstr()

        # Expand model paths containing iloc wildcards
        if not tree_for_idxcontext == {}:
            self.ipaths_consumed_for_name = _Worker.expand(
                self.ipath_consumed_for_name,
                tree_for_idxcontext,
                iconsumed_mpath_for_name,
            )

            self.rpaths_consumed_for_name = _Worker.expand(
                self.rpath_consumed_for_name,
                tree_for_idxcontext,
                rconsumed_mpath_for_name,
            )

            self.rpaths_provided_for_name = _Worker.expand(
                self.rpath_provided_for_name,
                tree_for_idxcontext,
                self.provided_mpath_for_name,
            )

            self.iname_for_path = {
                path: key
                for key, paths in self.ipaths_consumed_for_name.items()
                for path in traverse(paths)
            }

            self.rname_for_path = {
                path: key
                for key, paths in self.rpaths_consumed_for_name.items()
                for path in traverse(paths)
            }

        logging.info(f'Worker "{self.id}" was created for query "{self.query}"')

    @property
    def status(self):
        return "Not implemented"

    @staticmethod
    def bindings_from_idxs(bindings: List[HubitBinding], idxval_for_idxid) -> Dict:
        """
        replace index IDs with the actual indices
        if idxid from binding path not found in idxval_for_idxid it
        must correspond to a IDX_WILDCARD in the binding path.
        IDX_WILDCARD ignored in set_ilocs_on_path. Dealt with in expansion

        Returns path for name
        """
        if len(idxval_for_idxid) == 0:
            return {binding.name: binding.path for binding in bindings}
        else:
            result = {}
            for binding in bindings:
                indices = []
                for model_index_spec in binding.path.get_index_specifiers():
                    idxid = model_index_spec.identifier
                    range = model_index_spec.range
                    offset = model_index_spec.offset

                    index: Optional[str]
                    if range.is_digit:
                        # already an index so no transformation required
                        index = str(range)
                    elif range.is_empty:
                        # Map index ID to the value
                        index = str(int(idxval_for_idxid[idxid]) + offset)
                    elif range.is_full_range:
                        # leave for subsequent expansion.
                        # From the expansion method's perspective 'index' could be any character.
                        index = range
                    else:
                        raise HubitError(f"Unknown range '{range}'")
                    indices.append(ModelIndexSpecifier.from_components(idxid, index))

                result[binding.name] = binding.path.set_indices(indices, mode=1)
            return result

    @staticmethod
    def get_bindings(bindings: List[HubitBinding], query_path: HubitQueryPath):
        """Make symbolic binding specific i.e. replace index IDs
        with actual indices based on query

        Args:
            bindings: List of bindings
            query_path: Query path

        Raises:
            HubitWorkerError: Raised if query does not match any of the bindings
            or if query is not expanded

        Returns:
            [type]: TODO [description]
        """
        if query_path.wildcard_chr in query_path:
            raise HubitWorkerError(
                f"Query path '{query_path}' contains illegal character '{query_path.wildcard_chr}'. Should already have been expanded."
            )

        binding_paths = [binding.path for binding in bindings]
        # Get indices in binding_paths list that match the query
        idxs_match = query_path.idxs_for_matches(binding_paths)
        if len(idxs_match) == 0:
            fstr = 'Query "{}" did not match attributes provided by worker ({}).'
            raise HubitWorkerError(fstr.format(query_path, ", ".join(binding_paths)))

        # Get the location indices from query. Using the first binding path that
        # matched the query suffice
        idxval_for_idxid = {}
        for binding in bindings:
            if query_path.path_match(binding.path):
                identifiers = binding.path.get_index_identifiers()
                ranges = query_path.ranges()
                idxval_for_idxid.update(dict(zip(identifiers, ranges)))
                break

        path_for_name = _Worker.bindings_from_idxs(bindings, idxval_for_idxid)

        return path_for_name, idxval_for_idxid

    @staticmethod
    def expand(path_for_name, tree_for_idxcontext, model_path_for_name):
        paths_for_name = {}
        for name, path in path_for_name.items():
            tree = tree_for_idxcontext[model_path_for_name[name].index_context]
            pruned_tree = tree.prune_from_path(path, inplace=False)
            paths_for_name[name] = pruned_tree.expand_path(path)
        return paths_for_name

    def consumes_input_only(self):
        return self._consumes_input_only

    def binding_map(self, binding_type):
        return self.component.binding_map(binding_type)

    #     def make_map(bindings):
    #         return {binding.name: binding.path for binding in bindings}

    #     if type == "provides":  # provides is always present in worker
    #         return make_map(self.cfg["provides"])
    #     elif type in ("results", "input"):
    #         if _Worker.consumes_type(self.cfg, type):
    #             return make_map(self.cfg["consumes"][type])
    #         else:
    #             return {}
    #     else:
    #         raise HubitWorkerError(f'Unknown type "{type}"')

    # @staticmethod
    # def consumes_type(cfg: Dict, consumption_type: str) -> bool:
    #     """Check if configuration (cfg) consumes the "consumption_type"

    #     Args:
    #         cfg (Dict): Componet configuration
    #         consumption_type (str): The consumption type. Can either be "input" or "results". Validity not checked.

    #     Returns:
    #         bool: Flag indicating if the configuration consumes the "consumption_type"
    #     """
    #     return (
    #         "consumes" in cfg
    #         and consumption_type in cfg["consumes"]
    #         and len(cfg["consumes"][consumption_type]) > 0
    # )

    def paths_provided(self):
        """Generates a list of the (expanded) paths that will be provided.

        Returns:
            List: Sequence of paths that will be provided by the worker
        """
        return [
            path for paths in self.rpaths_provided_for_name.values() for path in paths
        ]

    def result_for_path(self):
        """
        Convert the results from internal attribute names to shared data names
        and expand ilocs
        """

        # TODO: Work only with : and not..... but not elegant...
        out = {}
        for name, paths in self.rpaths_provided_for_name.items():
            if len(paths) > 1:
                _out = {
                    path: val
                    for path, val in zip(traverse(paths), traverse(self.results[name]))
                }
            else:
                _out = {paths[0]: self.results[name]}
            out.update(_out)
        return out

    def results_ready(self):
        """
        Checks that all attributes provided have been calculated
        """
        return set(self.results.keys()) == set(self.rpath_provided_for_name.keys())

    def join(self):
        """Join process"""
        if self.job is not None:
            self.job.terminate()
            self.job.join()

    def use_cached_result(self, result):
        logging.info(f'Worker "{self.id}" using CACHE for query "{self.query}"')
        # Set each key-val pair from the cached results to the worker results
        # The worker results may be a managed dict
        for key, val in result.items():
            self.results[key] = val
        self._results_from = self.RESULTS_FROM_CACHE_ID

    def _func_wrapped(self, inputval_for_name, results, did_complete):
        self.func(inputval_for_name, results)
        with did_complete.get_lock():
            did_complete.value = Value(c_bool, True)
        self._callback_completed(self)

    def _mp_func(self, inputval_for_name):
        self.job = multiprocessing.Process(
            target=self._func_wrapped,
            args=(inputval_for_name, self.results, self._did_complete),
        )
        self.job.daemon = False
        self.job.start()

    def _sp_func(self, inputval_for_name):
        self.func(inputval_for_name, self.results)
        self._did_complete = True
        self._callback_completed(self)

    def _work_dryrun(self):
        """
        Sets all results to None
        """
        for name in self.rpath_provided_for_name.keys():
            tree = self.tree_for_idxcontext[
                self.provided_mpath_for_name[name].index_context
            ]
            self.results[name] = tree.none_like()

        self._did_complete = True
        self._callback_completed(self)

    def _work(self):
        """
        Executes actual work
        """
        logging.info(f'Worker "{self.id}" STARTED for query "{self.query}"')

        # Notify the hubit model that we are about to start the work
        # create single input
        inputval_for_name = ReadOnlyDict(
            {
                **self.inputval_for_name,
                **self.resultval_for_name,
            }
        )
        if self.use_multiprocessing:
            self._mp_func(inputval_for_name)
        else:
            self._sp_func(inputval_for_name)
        self._results_from = self.RESULTS_FROM_CALCULATION_ID

        logging.debug("\n**STOP WORKING**\n{}".format(self.__str__()))
        logging.info(f'Worker "{self.id}" finished for query "{self.query}"')

    @staticmethod
    def reshape(path_for_name, val_for_path):
        """
        Convert val_for_path to val_for_name i.e.
        from external names to internal names with expected shapes
        """
        return {
            name: reshape(path, val_for_path) for name, path in path_for_name.items()
        }

    def is_ready_to_work(self):
        return self._consumed_input_ready and self._consumed_results_ready

    def _prepare_work(self):
        logging.debug("Let the work begin: {}".format(self.workfun))
        self._consumed_data_set = True
        self._did_start = True

    def work(self):
        """ """
        self._prepare_work()
        self.workfun()

    def set_results(self, results):
        """Set pre-computed results directly on worker.
        Don't wait for input.
        """
        self._prepare_work()
        self.use_cached_result(results)
        self._did_complete = True
        self._callback_completed(self)

    def set_consumed_input(self, path: HubitQueryPath, value):
        if path in self.pending_input_paths:
            self.pending_input_paths.remove(path)
            self.inputval_for_path[path] = value
        self._consumed_input_ready = len(self.pending_input_paths) == 0

        # Create inputval_for_name as soon as we can to allow results_id to be formed
        if self._consumed_input_ready:
            self.inputval_for_name = _Worker.reshape(
                self.ipaths_consumed_for_name, self.inputval_for_path
            )

        if len(self.pending_input_paths) == 0:
            self.input_checksum = self._input_checksum()

        if self.is_ready_to_work():
            self.resultval_for_name = _Worker.reshape(
                self.rpaths_consumed_for_name, self.resultval_for_path
            )
            self.results_checksum = self._results_checksum()
            self._callback_ready(self)

        # if not self.caching:
        #     self.work_if_ready()

    def set_consumed_result(self, path, value):
        if path in self.pending_results_paths:
            self.pending_results_paths.remove(path)
            self.resultval_for_path[path] = value

        self._consumed_results_ready = len(self.pending_results_paths) == 0

        if self.is_ready_to_work():
            self.resultval_for_name = _Worker.reshape(
                self.rpaths_consumed_for_name, self.resultval_for_path
            )
            self.results_checksum = self._results_checksum()

            self._callback_ready(self)

    def set_values(self, inputdata, resultsdata: FlatData):
        """
        Set the consumed values if they are ready otherwise add them
        to the list of pending items
        """
        # Check consumed input (should not have any pending items by definition)
        for path in self.iname_for_path.keys():
            if path in inputdata.keys():
                self.inputval_for_path[path] = inputdata[path]
            else:
                self.pending_input_paths.append(path)

        # Check consumed results
        for path in self.rname_for_path.keys():
            if path in resultsdata.keys():
                self.resultval_for_path[path] = resultsdata[path]
            else:
                self.pending_results_paths.append(path)

        self._consumed_input_ready = len(self.pending_input_paths) == 0
        self._consumed_results_ready = len(self.pending_results_paths) == 0

        # Create inputval_for_name as soon as we can to allow results_id to be formed
        if self._consumed_input_ready:
            self.inputval_for_name = _Worker.reshape(
                self.ipaths_consumed_for_name, self.inputval_for_path
            )
            self.input_checksum = self._input_checksum()

        if self._consumed_results_ready:
            self.resultval_for_name = _Worker.reshape(
                self.rpaths_consumed_for_name, self.resultval_for_path
            )
            self.results_checksum = self._results_checksum()

        if self.is_ready_to_work():
            self._callback_ready(self)

        return (
            copy.copy(self.pending_input_paths),
            copy.copy(self.pending_results_paths),
        )

    def idstr(self):
        """
        Make an ID string for the worker class that will be the same
        if all ilocs are the same for the same component
        """
        return "name={} v{} idxs={}".format(
            self.id,
            self.version,
            "&".join([f"{k}={v}" for k, v in self.idxval_for_idxid.items()]),
        )

    def _input_checksum(self) -> str:
        """checksum for the input values"""
        return hashlib.md5(
            # f'{self.inputval_for_name}_{id(self.func)}'.encode('utf-8')
            json.dumps(
                [
                    sorted(self.inputval_for_name.items(), key=itemgetter(0)),
                    str(self.component.path),
                    self.func.__name__,
                ]
            ).encode()
        ).hexdigest()

    def _results_checksum(self) -> str:
        """
        We want to know the checksum before the results values are available.
        The results will be identifiable by
          - the worker input (input_checksum)
          - the consumed results
        """
        return hashlib.md5(
            json.dumps(
                [
                    self.input_checksum,
                    sorted(self.resultval_for_name.items(), key=itemgetter(0)),
                ]
            ).encode()
        ).hexdigest()

    def __str__(self):
        n = 100
        fstr1 = "{:30}{}\n"
        strtmp = "=" * n + "\n"
        strtmp += "ID: {}\n".format(self.idstr())
        strtmp += "Function: {}\n".format(self.func)
        strtmp += "Query: {}\n".format(self.query)
        strtmp += "-" * n + "\n"
        strtmp += fstr1.format("Results provided", self.rpath_provided_for_name)
        strtmp += fstr1.format(
            "Results provided expanded", self.rpaths_provided_for_name
        )
        strtmp += fstr1.format("Input consumed", self.ipath_consumed_for_name)
        strtmp += fstr1.format("Input consumed expanded", self.ipaths_consumed_for_name)
        strtmp += fstr1.format("Results consumed", self.rpath_consumed_for_name)
        strtmp += fstr1.format(
            "Results consumed expanded", self.rpaths_consumed_for_name
        )

        strtmp += "-" * n + "\n"
        strtmp += fstr1.format("Input attr values", self.inputval_for_name)
        strtmp += fstr1.format("Input path values", self.inputval_for_path)
        strtmp += fstr1.format("Results attr values", self.resultval_for_name)
        strtmp += fstr1.format("Results path values", self.resultval_for_path)
        strtmp += fstr1.format("Input pending", self.pending_input_paths)
        strtmp += fstr1.format("Results pending", self.pending_results_paths)

        strtmp += "-" * n + "\n"
        strtmp += f"Ready to work: {self.is_ready_to_work()}\n"
        strtmp += f"Did start: {self._did_start}\n"
        strtmp += f"Did complete: {self._did_complete}\n"
        strtmp += "Results {}\n".format(self.results)
        strtmp += f"Results from: {self._results_from}\n"

        strtmp += "=" * n + "\n"

        return strtmp

    def used_cache(self):
        return self._results_from == self.RESULTS_FROM_CACHE_ID
