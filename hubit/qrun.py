from __future__ import annotations
from collections import defaultdict
import copy
from importlib.machinery import ModuleSpec
from importlib.util import spec_from_file_location, module_from_spec
from importlib.abc import Loader
import importlib
import logging
from multiprocessing.managers import SyncManager
import os
import sys
import time
from types import ModuleType
from typing import Any, Callable, Dict, List, Set, Tuple, Optional, Union, cast
import yaml
from threading import Thread, Event

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hubit.model import HubitModel

from .worker import _Worker
from .utils import count
from .config import FlatData, HubitModelComponent, HubitQueryPath

POLLTIME = 0.1
POLLTIME_LONG = 0.25


class ModuleInterface(ModuleType):
    @staticmethod
    def version() -> str:
        ...


def module_from_path(module_name: str, file_path: str) -> ModuleInterface:
    spec = spec_from_file_location(module_name, file_path)
    # https://github.com/python/typeshed/issues/2793
    assert isinstance(spec, ModuleSpec)
    assert isinstance(spec.loader, Loader)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(ModuleInterface, module)


def module_from_dotted_path(dotted_path: str) -> ModuleInterface:
    return cast(ModuleInterface, importlib.import_module(dotted_path))


class _QueryRunner:
    def __init__(
        self,
        model: HubitModel,
        use_multi_processing: bool,
        component_caching: bool = False,
    ):
        """Internal class managing workers. Is in a model, the query runner
        is responsible for deploying and book keeping workers according
        to a query specified to the model.

        Args:
            model (HubitModel): The model to manage
            use_multi_processing (bool): Flag indicating if multi-processing should be used
        """
        self.model = model
        self.use_multi_processing = use_multi_processing
        self.workers: List[_Worker] = []
        self.workers_working: List[_Worker] = []
        self.workers_completed: List[_Worker] = []
        self.worker_for_id: Dict[str, _Worker] = {}
        self.subscribers_for_path: Dict[HubitQueryPath, List[_Worker]] = {}
        self.component_caching: bool = component_caching
        self.flat_results: FlatData = FlatData()
        self.manager: Optional[SyncManager] = None

        # For book-keeping what has already been imported
        # {component_id: (func, version)}
        self._components: Dict[str, Tuple[Callable, str]] = {}

        # For book-keeping which results have already been calculated
        # {checksum: worker.results}
        self.results_for_results_checksum: Dict[str, Dict[str, Any]] = {}

        # To track if there is already a provider for the results. Elements are checksums
        self.results_checksum_for_worker: Dict[_Worker, str] = {}
        self.subscribers_for_results_checksum: Dict[str, List[_Worker]] = defaultdict(
            list
        )

    def _worker_status(self, worker):
        return "(complete)" if worker in self.workers_completed else "(waiting )"

    def __str__(self):
        worker_ids: List[List[str]] = []

        headers = [f"Workers spawned ({len(self.workers)}) & results ID"]
        tmp = []
        for worker in self.workers:
            try:
                results_checksum = self.results_checksum_for_worker[worker]
            except KeyError:
                results_checksum = "Not available"
            arrow = "<-" if worker.used_cache() else "->"
            status = self._worker_status(worker)
            s = f"{worker.query} -> {worker.idstr()} {status} {arrow} {results_checksum}"
            tmp.append(s)
        worker_ids.append(tmp)
        lines = [f"\n*** {headers[-1]} ***"]
        lines.extend([str(worker) for worker in self.workers])

        headers.append(f"Paths ({len(self.subscribers_for_path)}) with subscribers")
        tmp = [
            f"{query}: {', '.join(f'{subscriber.idstr()} {self._worker_status(subscriber)}' for subscriber in subscribers)}"
            for query, subscribers in self.subscribers_for_path.items()
        ]
        if len(tmp) == 0:
            tmp = ["None"]
        worker_ids.append(tmp)

        lines += [f"*" * 100]
        lines.append(f"Use component caching: {self.component_caching}")
        lines.append(f"Use multi-procesing: {self.use_multi_processing}")
        for header, wids in zip(headers, worker_ids):
            lines.append(header)
            lines.extend([f"   {wid}" for wid in wids])
        lines += [f"*" * 100]
        return "\n".join(lines)

    def reset(self, flat_results: Optional[FlatData] = None):
        self.workers = []
        self.workers_working = []
        self.workers_completed = []
        self.worker_for_id = {}
        self.subscribers_for_path = {}

        if flat_results is None:
            self.flat_results = FlatData()
        else:
            self.flat_results = flat_results

    def _join_workers(self):
        # TODO Not sure this is required
        for i, worker in enumerate(self.workers_completed):
            # https://stackoverflow.com/questions/25455462/share-list-between-process-in-python-server
            worker.join()

    @staticmethod
    def _get_func(
        base_path,
        component_cfg: HubitModelComponent,
        components: Dict[str, Tuple[Callable, str]],
    ):
        """[summary]

        Args:
            base_path (str): Model base path
            component_cfg (HubitModelComponent): configuration data from the model definition file
            components (Dict):

        Returns:
            tuple: function handle, function version, and component dict
        """
        version: str
        func_name = component_cfg.func_name
        if not component_cfg.is_dotted_path:
            path, file_name = os.path.split(component_cfg.path)
            path = os.path.join(base_path, path)
            module_name = os.path.splitext(file_name)[0]
            path = os.path.abspath(path)
            file_path = os.path.join(path, file_name)
            component_id = component_cfg.id
            if component_id in components.keys():
                func, version = components[component_id]
                return func, version, components

            sys.path.insert(0, path)
            module = module_from_path(module_name, file_path)
        else:
            module = module_from_dotted_path(component_cfg.path)
            component_id = component_cfg.id
            if component_id in components.keys():
                func, version = components[component_id]
                return func, version, components

        func = getattr(module, func_name)
        try:
            version = module.version()
        except AttributeError:
            version = "None"
        components[component_id] = func, version
        return func, version, components

    def _worker_for_query(
        self,
        path: HubitQueryPath,
        dryrun: bool = False,
    ) -> _Worker:
        """Creates instance of the worker class that can respond to the query

        Args:
            path: Explicit query path
            dryrun (bool, optional): Dryrun flag for the worker. Defaults to False.

        Raises:
            HubitModelQueryError: Multiple providers for the query
            HubitModelQueryError: No providers for the query

        Returns:
            _Worker instance or None
        """
        component = self.model.component_for_qpath(path)
        (func, version, self._components) = _QueryRunner._get_func(
            self.model.base_path, component, self._components
        )

        # Create and return worker
        return _Worker(
            self,
            component,
            path,
            func,
            version,
            self.model.tree_for_idxcontext,
            self.manager,
            dryrun=dryrun,
            caching=self.component_caching,
        )

    @staticmethod
    def _transfer_input(
        input_paths: List[HubitQueryPath],
        worker: _Worker,
        extracted_input: Dict,
        all_input: FlatData,
    ):
        """
        Transfer required input from all input to extracted input
        and to worker
        """
        for path in input_paths:
            val = all_input[path]
            extracted_input[path] = val
            worker.set_consumed_input(path, val)

    def spawn_workers(
        self,
        qpaths: List[HubitQueryPath],
        extracted_input,
        all_input,
        skip_paths=[],
        dryrun=False,
    ):
        """Create workers

        queries should be expanded i.e. explicit in terms of iloc

        qpaths are internal (dot-path)

        paths in skip_paths are skipped
        """
        _skip_paths = copy.copy(skip_paths)
        for qpath in qpaths:
            # Skip if the queried data will be provided
            if qpath in _skip_paths:
                continue

            # Check whether the queried data is already available
            if qpath in self.flat_results:
                continue

            # Figure out which component can provide a response to the query
            # and get the corresponding worker
            worker = self._worker_for_query(qpath, dryrun=dryrun)

            # Skip if the queried data will be provided
            _skip_paths.extend(worker.paths_provided())

            # Check that another query path did not already request this worker
            if worker._id in self.worker_for_id.keys():
                continue

            self.worker_for_id[worker._id] = worker

            # Set available data on the worker. If data is missing the corresponding
            # paths (queries) are returned
            (input_paths_missing, queries_next) = worker.set_values(
                extracted_input, self.flat_results
            )

            # THIS WILL START THE WORKER BUT WE DONT WANT THAT
            # IF ANOTHER WORKER IS ALREADY CALCULATING THAT
            # TODO: Not sure extracted_input is still useful
            self._transfer_input(
                input_paths_missing, worker, extracted_input, all_input
            )

            # Expand requirement paths returned when the worker was filled
            # with input that is currently available
            qpaths_next_exp = [
                qstrexp
                for qstr in queries_next
                for qstrexp in self.model._expand_query(
                    qstr, store=False
                ).flat_expanded_paths()
            ]
            logging.debug("qpaths_next: {}".format(qpaths_next_exp))

            # Add the worker to the subscribers list for that query in order
            for path_next in qpaths_next_exp:
                if not (path_next in self.subscribers_for_path):
                    self.subscribers_for_path[path_next] = []
                self.subscribers_for_path[path_next].append(worker)

            # Spawn workers for the dependencies
            self.spawn_workers(
                queries_next,
                extracted_input,
                all_input,
                skip_paths=_skip_paths,
                dryrun=dryrun,
            )

    def _set_results(self, worker: _Worker, results_checksum: str):
        # Start worker to handle transfer of results to correct paths
        worker.set_results(self.results_for_results_checksum[results_checksum])

        # If the worker subscribes to path remove the subscription
        for subscribers in self.subscribers_for_path.values():
            if worker in subscribers:
                subscribers.remove(worker)

        # Remove elements with no subscribers. Not necessary but aids debugging
        self.subscribers_for_path = {
            k: v for k, v in self.subscribers_for_path.items() if len(v) > 0
        }

    def report_for_duty(self, worker: _Worker):
        """
        Start worker or add it to the list of workers waiting for a provider
        """
        checksum = worker.results_checksum
        logging.info(
            f"Worker '{worker.id}' reported for duty for query '{worker.query}'. Will produce result with checksum '{checksum}'"
        )
        assert (
            checksum is not None
        ), "Only a worker with all input data is ready to work"

        if self.component_caching:
            if checksum in self.results_checksum_for_worker.values():
                self.results_checksum_for_worker[worker] = checksum
                # provided will be (is) calculated by another worker
                if checksum in self.results_for_results_checksum.keys():
                    # result is already calculated
                    self._set_results(worker, checksum)
                else:
                    # result not calculated yet but will be provided by another worker. Subscribe to the result
                    self.subscribers_for_results_checksum[checksum].append(worker)
            else:
                # There is no provider yet so this worker should be registered as the provider
                self.results_checksum_for_worker[worker] = checksum
                worker.work()
        else:
            # checksums not needed but nice for debugging
            self.results_checksum_for_worker[worker] = checksum
            worker.work()

    def report_completed(self, worker: _Worker):
        logging.info(
            f"Worker '{worker.id}' with checksum '{worker.results_checksum}' for query '{worker.query}' completed"
        )
        self._set_worker_completed(worker)

    def _set_worker(self, worker: _Worker):
        """
        Called from _Worker object when the input is set.
        Not on init since we do not yet know if a similar
        object exists.
        """
        self.workers.append(worker)

    def _set_worker_working(self, worker: _Worker):
        """
        Called from _Worker object just before the worker
        process is started.
        """
        self.workers_working.append(worker)

    def _set_worker_completed(self, worker: _Worker):
        """
        Called when results attribute has been populated
        """
        self.workers_working.remove(worker)
        self.workers_completed.append(worker)
        self._transfer_results(worker)

        if self.component_caching:
            # Store results from worker on the calculation ID
            logging.info(
                f"Worker '{worker.id}' registers results with checksum '{worker.results_checksum}' for query '{worker.query}'"
            )
            checksum = worker.results_checksum

            # If worker is complete the checksum should be generated. This check is superfluous but satisfies mypy
            assert checksum is not None

            self.results_for_results_checksum[checksum] = worker.results
            # If all results have been calculated no more messages will be sent to workers
            # So we need to start them manually
            if checksum in self.subscribers_for_results_checksum.keys():
                # There are subscribers
                for _worker in self.subscribers_for_results_checksum[checksum]:
                    self._set_results(_worker, checksum)

                # All subscribers have had their results set so remove their
                del self.subscribers_for_results_checksum[checksum]

        # Save results to disk
        if self.model._model_caching_mode == "incremental":
            with open(self.model._cache_file_path, "w") as handle:
                self.flat_results.to_file(self.model._cache_file_path)

    def _transfer_results(self, worker: _Worker):
        """
        Transfer results and notify subscribers. Called from workflow.
        """
        results = worker.result_for_path()
        # sets results on subscribers
        for path, value in results.items():
            if path in self.subscribers_for_path.keys():
                for subscriber in self.subscribers_for_path[path]:
                    subscriber.set_consumed_result(path, value)
            self.flat_results[path] = value

    def prepare(self):
        self.t_start = time.perf_counter()

    def wait(self, _queries):
        if self.use_multi_processing:
            # Start thread that periodically checks whether we are finished or not
            shutdown_event = Event()
            watcher = Thread(target=self._watcher, args=(_queries, shutdown_event))
            watcher.daemon = True
            watcher.start()
            watcher.join()
            return shutdown_event
        else:
            return None

    def close(self):
        elapsed_time = self._add_log_items(self.t_start)
        logging.info("Response created in {} s".format(elapsed_time))
        # self.flat_results = FlatData.from_flat_dict(self.flat_results)

        # Save results
        if self.model._model_caching_mode == "after_execution":
            self.flat_results.to_file(self.model._cache_file_path)

    def _watcher(self, queries, shutdown_event):
        """
        Run this watcher on a thread. Runs until all queried data
        is present in the results. Not needed for sequential runs,
        but is necessary when main tread should waiting for
        calculation processes when using multiprocessing
        """
        should_stop = False
        while not should_stop and not shutdown_event.is_set():

            if self.use_multi_processing:
                self._poll_workers()

            should_stop = all([query in self.flat_results.keys() for query in queries])
            time.sleep(POLLTIME)

    def _poll_workers(self):
        """
        Getting results from workers must happen from main thread to avoid
        concurency issues.

        TODO: negative-indices. could we make the flat data a Syncmanager dict and write directly
        from the worker process. This could be done by wrapping the worker func.
        would make it parallel vs sequential more symmetric
        """
        _workers_completed = [
            worker for worker in self.workers_working if worker.results_ready()
        ]
        for worker in _workers_completed:
            logging.debug("Query runner detected that a worker completed.")
            self.report_completed(worker)

    def _add_log_items(self, t_start: float) -> float:
        # Set zeros for all components
        worker_counts = {
            component.name: 0 for component in self.model.model_cfg.components
        }
        worker_counts.update(count(self.workers, key_from="name"))

        # Set zeros for all components
        cache_counts = {
            component.name: 0 for component in self.model.model_cfg.components
        }
        cache_counts.update(
            count(
                self.workers,
                key_from="name",
                increment_fun=(lambda item: 1 if item.used_cache() else 0),
            )
        )
        elapsed_time = time.perf_counter() - t_start
        self.model._add_log_items(worker_counts, elapsed_time, cache_counts)
        return elapsed_time
