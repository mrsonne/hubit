from __future__ import annotations
import os
import pickle
import hashlib
import logging
import multiprocessing
import copy
from typing import Callable, Dict, Set, TYPE_CHECKING, List
from .config import HubitBinding, HubitModelPath
from .shared import (
    LengthTree,
    idxs_for_matches,
    check_path_match,
    get_iloc_indices,
    traverse,
    reshape,
)
from .errors import HubitWorkerError

if TYPE_CHECKING:
    from .qrun import _QueryRunner
    from .shared import HubitModelComponent


class _Worker:
    """ """

    RESULTS_FROM_CACHE_ID = "cache"
    RESULTS_FROM_CALCULATION_ID = "calculation"
    RESULTS_FROM_UNKNOWN = "unknown"

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
            return {
                binding.name: binding.path.set_indices(
                    [
                        idxval_for_idxid[idxid] if idxid in idxval_for_idxid else None
                        for idxid in binding.path.get_index_identifiers()
                    ],
                )
                for binding in bindings
            }

    @staticmethod
    def get_bindings(bindings: List[HubitBinding], query_path):
        """Make symbolic binding specific i.e. replace index IDs
        with actual indices based on query

        Args:
            bindings (List[str]): List of bindings
            query_path (str): Query path
            idxids: TODO

        Raises:
            HubitWorkerError: Raised if query does not match any of the bindings

        Returns:
            [type]: TODO [description]
        """
        binding_paths = [binding.path for binding in bindings]
        # Get indices in binding_paths list that match the query
        idxs = idxs_for_matches(query_path, binding_paths, accept_idx_wildcard=False)
        if len(idxs) == 0:
            fstr = 'Query "{}" did not match attributes provided by worker ({}).'
            raise HubitWorkerError(fstr.format(query_path, ", ".join(binding_paths)))

        # Get the location indices from query. Using the first binding path that
        # matched the query suffice
        idxval_for_idxid = {}
        for binding in bindings:
            if check_path_match(query_path, binding.path, accept_idx_wildcard=False):
                idxids = binding.path.get_index_identifiers()
                idxs = get_iloc_indices(
                    HubitModelPath.as_internal(query_path),
                    HubitModelPath.as_internal(binding.path),
                    idxids,
                )
                idxval_for_idxid.update(dict(zip(idxids, idxs)))
                break

        path_for_name = _Worker.bindings_from_idxs(bindings, idxval_for_idxid)

        return path_for_name, idxval_for_idxid

    @staticmethod
    def expand(path_for_name, tree_for_idxcontext, model_path_for_name):
        paths_for_name = {}
        for name, path in path_for_name.items():
            tree = tree_for_idxcontext[model_path_for_name[name].get_idx_context()]
            pruned_tree = tree.prune_from_path(
                HubitModelPath.as_internal(path),
                HubitModelPath.as_internal(model_path_for_name[name]),
                inplace=False,
            )

            paths_for_name[name] = pruned_tree.expand_path(path, as_internal_path=True)
        return paths_for_name

    def __init__(
        self,
        manager: multiprocessing.Manager,
        qrun: _QueryRunner,
        component: HubitModelComponent,
        query: HubitModelPath,
        func: Callable,
        version: str,
        tree_for_idxcontext: Dict[str, LengthTree],
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
        self.name = component.id  # name of the component
        self.version = version  # Version of the component
        self.qrun = qrun  # reference to the query runner
        self.job = None  # For referencing the job if using multiprocessing
        self.query = query
        self.tree_for_idxcontext = tree_for_idxcontext
        self.component = component
        self._consumed_data_set = False
        self._consumed_input_ready = False
        self._consumed_results_ready = False
        self._consumes_input_only = False
        self._results_id = None
        self.caching = caching

        # Store information on how results were created (calculation or cache)
        self._results_from = self.RESULTS_FROM_UNKNOWN

        if dryrun:
            # If worker should perform a dry run set the worker function to "work_dryrun"
            self.workfun = self.work_dryrun
        else:
            self.workfun = self.work

        # Paths for values that are consumed but not ready
        self.pending_input_paths = []
        self.pending_results_paths = []

        # Stores required values using internal names as keys
        self.inputval_for_name = {}
        self.resultval_for_name = {}

        # Stores required values using internal names as keys
        self.inputval_for_path = {}
        self.resultval_for_path = {}

        # Which indices are specified for each index ID
        self.idxval_for_idxid = {}

        if manager is None:
            self.results = {}
            self.use_multiprocessing = False
        else:
            self.results = manager.dict()
            self.use_multiprocessing = True

        # TODO
        # 1) Prune tree corresponding to query
        # 2) Prune remaining trees based idxval_for_idxid (method does no exist yet on LengthTree)

        # TODO: assumes provider has the all ilocs defined.
        # Model path for input provisions with ilocs from query
        if self.component.does_provide_results():
            self.rpath_provided_for_name, self.idxval_for_idxid = _Worker.get_bindings(
                self.component.provides_results, query
            )
            self.provided_mpath_for_name = self.component.binding_map(
                "provides_results"
            )
        else:
            self.provided_mpath_for_name = None
            raise HubitWorkerError(
                'No provider for Hubit \
                                     model component "{}"'.format(
                    self.name
                )
            )

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

        logging.info(f'Worker "{self.name}" was deployed for query "{self.query}"')

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

    def work_dryrun(self):
        """
        Sets all results to None
        """
        self.qrun._set_worker_working(self)
        for name in self.rpath_provided_for_name.keys():
            tree = self.tree_for_idxcontext[
                self.provided_mpath_for_name[name].get_idx_context()
            ]
            self.results[name] = tree.none_like()

    def join(self):
        """Join process"""
        if self.job is not None:
            self.job.terminate()
            self.job.join()

    def use_cached_result(self, result):
        logging.info(f'Worker "{self.name}" using CACHE for query "{self.query}"')
        self.qrun._set_worker_working(self)
        # Set each key-val pair from the cached results to the worker results
        # The worker results may be a managed dict
        for key, val in result.items():
            self.results[key] = val
        self._results_from = self.RESULTS_FROM_CACHE_ID

    def work(self):
        """
        Executes actual work
        """
        logging.info(f'Worker "{self.name}" STARTED for query "{self.query}"')

        # Notify the hubit model that we are about to start the work
        self.qrun._set_worker_working(self)
        if self.use_multiprocessing:
            self.job = multiprocessing.Process(
                target=self.func,
                args=(self.inputval_for_name, self.resultval_for_name, self.results),
            )
            self.job.daemon = False
            self.job.start()
        else:
            self.func(self.inputval_for_name, self.resultval_for_name, self.results)
        self._results_from = self.RESULTS_FROM_CALCULATION_ID

        logging.debug("\n**STOP WORKING**\n{}".format(self.__str__()))
        logging.info(f'Worker "{self.name}" finished for query "{self.query}"')

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

    def work_if_ready(self, results=None):
        """
        If all consumed attributes are present start working
        """
        if self.is_ready_to_work():
            logging.debug("Let the work begin: {}".format(self.workfun))

            self.resultval_for_name = _Worker.reshape(
                self.rpaths_consumed_for_name, self.resultval_for_path
            )

            self._consumed_data_set = True
            if results is None:
                self.workfun()
            else:
                self.use_cached_result(results)

    def set_consumed_input(self, path, value):
        if path in self.pending_input_paths:
            self.pending_input_paths.remove(path)
            self.inputval_for_path[path] = value
        self._consumed_input_ready = len(self.pending_input_paths) == 0

        # Create inputval_for_name as soon as we can to allow results_id to be formed
        if self._consumed_input_ready:
            self.inputval_for_name = _Worker.reshape(
                self.ipaths_consumed_for_name, self.inputval_for_path
            )

        # if not self.caching:
        #     self.work_if_ready()

    def set_consumed_result(self, path, value):
        if path in self.pending_results_paths:
            self.pending_results_paths.remove(path)
            self.resultval_for_path[path] = value

        self._consumed_results_ready = len(self.pending_results_paths) == 0
        self.work_if_ready()

    def set_values(self, inputdata, resultsdata):
        """
        Set the consumed values if they are ready otherwise add them
        to the list of pending items
        """
        # set the worker here since in init we have not yet checked that a similar instance does not exist
        self.qrun._set_worker(self)

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
            self.name,
            self.version,
            "&".join([f"{k}={v}" for k, v in self.idxval_for_idxid.items()]),
        )

    def _make_results_id(self):
        """results_ids based on input and function only"""
        return hashlib.md5(
            # f'{self.inputval_for_name}_{id(self.func)}'.encode('utf-8')
            pickle.dumps([self.inputval_for_name, id(self.func)])
        ).hexdigest()

    def set_results_id(self, results_ids: Set[str]) -> str:
        """results_ids are the IDs of workers spawned from the
        current worker

        augment that with worker's own results_id
        """
        results_ids.add(self._make_results_id())
        self._results_id = hashlib.md5("".join(results_ids).encode("utf-8")).hexdigest()
        return self._results_id

    @property
    def results_id(self):
        return self._results_id or self._set_results_id()

    def _set_results_id(self):
        """checksum for worker function and input. This ID is identical for
        worker that carry out the same calculation
        """
        if self._results_id is not None:
            return self._results_id

        if not self._consumes_input_only:
            raise HubitWorkerError("Not safe to create results ID")

        if not self._consumed_input_ready:
            raise HubitWorkerError("Not enough data to create calc ID")

        self._results_id = self._make_results_id()
        return self._results_id

    def __str__(self):
        n = 100
        fstr1 = "R provided {}\nR provided exp {}\nI consumed {}\nI consumed exp {}\nR consumed {}\nR consumed exp {}\n"
        fstr2 = "I attr values {}\nI path values {}\nR attr values {}\nR path values {}\nI pending {}\nR pending {}\n"
        strtmp = "=" * n + "\n"
        strtmp += "ID {}\n".format(self.idstr())
        strtmp += "Function {}\n".format(self.func)
        strtmp += "-" * n + "\n"
        strtmp += fstr1.format(
            self.rpath_provided_for_name,
            self.rpaths_provided_for_name,
            self.ipath_consumed_for_name,
            self.ipaths_consumed_for_name,
            self.rpath_consumed_for_name,
            self.rpaths_consumed_for_name,
        )
        strtmp += "-" * n + "\n"
        strtmp += fstr2.format(
            self.inputval_for_name,
            self.inputval_for_path,
            self.resultval_for_name,
            self.resultval_for_path,
            self.pending_input_paths,
            self.pending_results_paths,
        )
        strtmp += "-" * n + "\n"
        strtmp += "Results {}\n".format(self.results)

        strtmp += "=" * n + "\n"

        return strtmp

    def used_cache(self):
        return self._results_from == self.RESULTS_FROM_CACHE_ID
