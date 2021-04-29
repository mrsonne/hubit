import copy
import importlib
import logging
import os
import sys
import time
from typing import Any, Dict, List, Set
import yaml
from .worker import _Worker
from .shared import count
from .config import FlatData, HubitModelComponent

POLLTIME = 0.1
POLLTIME_LONG = 0.25


class _QueryRunner:
    def __init__(self, model, use_multi_processing, component_caching=False):
        """Internal class managing workers. Is in a model, the query runner
        is responsible for deploying and book keeping workers according
        to a query specified to the model.

        Args:
            model (HubitModel): The model to manage
            use_multi_processing (bool): Flag indicating if multi-processing should be used
        """
        self.model = model
        self.use_multi_processing = use_multi_processing
        self.workers = []
        self.workers_working = []
        self.workers_completed = []
        self.worker_for_id = {}
        self.observers_for_query = {}
        self.component_caching = component_caching

        # For book-keeping what has already been imported
        self._components = {}

        # For book-keeping which calculations have already been calculated
        self.results_for_results_id = {}
        # self.provider_for_results_id: Dict[str, _Worker] = {}
        self.provided_results_id = set()
        self.subscribers_for_results_id: Dict[str, List[_Worker]] = {}

    def _join_workers(self):
        # TODO Not sure this is required
        for i, worker in enumerate(self.workers_completed):
            # https://stackoverflow.com/questions/25455462/share-list-between-process-in-python-server
            worker.join()

    @staticmethod
    def _get_func(base_path, component_cfg: HubitModelComponent, components):
        """[summary]

        Args:
            base_path (str): Model base path
            component_cfg (HubitModelComponent): configuration data from the model definition file
            components (Dict):

        Returns:
            tuple: function handle, function version, and component dict
        """
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
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        else:
            module = importlib.import_module(component_cfg.path)
            component_id = component_cfg.id
            if component_id in components.keys():
                func, version = components[component_id]
                return func, version, components

        func = getattr(module, func_name)
        try:
            version = module.version()
        except AttributeError:
            version = None
        components[component_id] = func, version
        return func, version, components

    def _worker_for_query(self, manager, query_path: str, dryrun: bool = False) -> Any:
        """Creates instance of the worker class that can respond to the query

        Args:
            query_path (str): Explicit path
            dryrun (bool, optional): Dryrun flag for the worker. Defaults to False.

        Raises:
            HubitModelQueryError: Multiple providers for the query
            HubitModelQueryError: No providers for the query

        Returns:
            Any: _Worker or None
        """

        component_id = self.model._cmpname_for_query(query_path)
        component = self.model.component_for_name(component_id)
        (func, version, self._components) = _QueryRunner._get_func(
            self.model.base_path, component, self._components
        )

        # Create and return worker
        try:
            return _Worker(
                manager,
                self,
                component,
                query_path,
                func,
                version,
                self.model.tree_for_idxcontext,
                dryrun=dryrun,
                caching=self.component_caching,
            )
        except RuntimeError:
            return None

    @staticmethod
    def _transfer_input(input_paths, worker, inputdata, all_input):
        """
        Transfer required input from all input to extracted input
        and to worker
        """
        for path in input_paths:
            val = all_input[path]
            inputdata[path] = val
            worker.set_consumed_input(path, val)

    def spawn_workers(
        self,
        manager,
        qpaths,
        extracted_input,
        flat_results: FlatData,
        all_input,
        skip_paths=[],
        dryrun=False,
    ) -> Set[str]:
        """Create workers

        queries should be expanded i.e. explicit in terms of iloc

        qpaths are internal (dot-path)

        paths in skip_paths are skipped
        """
        _skip_paths = copy.copy(skip_paths)
        results_ids = set()
        for qpath in qpaths:
            # Skip if the queried data will be provided
            if qpath in _skip_paths:
                continue

            # Check whether the queried data is already available
            if qpath in flat_results:
                continue

            # Figure out which component can provide a response to the query
            # and get the corresponding worker
            worker = self._worker_for_query(manager, qpath, dryrun=dryrun)
            # if worker is None: return False

            # Skip if the queried data will be provided
            _skip_paths.extend(worker.paths_provided())

            # Check that another query path did not already request this worker
            if worker._id in self.worker_for_id.keys():
                continue

            self.worker_for_id[worker._id] = worker

            # Set available data on the worker. If data is missing the corresponding
            # paths (queries) are returned
            (input_paths_missing, queries_next) = worker.set_values(
                extracted_input, flat_results
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
                for qstrexp in self.model._expand_query(qstr)
            ]
            logging.debug("qpaths_next: {}".format(qpaths_next_exp))

            # Add the worker to the observers list for that query in order
            for path_next in qpaths_next_exp:
                if not path_next in self.observers_for_query:
                    self.observers_for_query[path_next] = []
                self.observers_for_query[path_next].append(worker)

            # Spawn workers for the dependencies
            results_ids_sub_workers = self.spawn_workers(
                manager,
                queries_next,
                extracted_input,
                flat_results,
                all_input,
                skip_paths=_skip_paths,
                dryrun=dryrun,
            )
            # Update with IDs for sub-workers
            results_id_current = self._submit_worker(worker, results_ids_sub_workers)
            results_ids.add(results_id_current)

        return results_ids

    def _submit_worker(
        self, worker: _Worker, results_ids_sub_workers: List[str]
    ) -> str:
        """
        Start worker or add it to the list of workers waiting for a provider
        """
        # if not success: return False
        if self.component_caching:
            if worker.consumes_input_only():
                results_id = worker.results_id
            else:
                # set the worker's results id based on result ids of sub-workers
                results_id = worker.set_results_id(results_ids_sub_workers)

            # if results_id in self.provider_for_results_id:
            if results_id in self.provided_results_id:
                # there is a provider for the results
                if results_id in self.results_for_results_id:
                    # The results are already there.
                    # Start worker to handle transfer of results to correct paths
                    worker.work_if_ready(self.results_for_results_id[results_id])
                else:
                    # Register as subscriber for the results
                    if not results_id in self.subscribers_for_results_id:
                        self.subscribers_for_results_id[results_id] = []
                    self.subscribers_for_results_id[results_id].append(worker)

            else:
                # There is no provider yet so this worker should be registered as the provider
                # self.provider_for_results_id[results_id] = worker
                self.provided_results_id.add(results_id)
                worker.work_if_ready()

        else:
            worker.work_if_ready()
            results_id = "NA"
        return results_id

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

    # def get_cache(self, worker_calc_id):
    #     """
    #     Called from worker when all consumed data is set
    #     """
    #     return self.results_for_results_id[worker_calc_id]

    def _set_worker_completed(self, worker: _Worker, flat_results):
        """
        Called when results attribute has been populated
        """

        self.workers_completed.append(worker)
        self._transfer_results(worker, flat_results)
        if self.component_caching:
            results_id = worker.results_id

            # Store results from worker on the calculation ID
            self.results_for_results_id[results_id] = worker.results

            if results_id in self.subscribers_for_results_id.keys():
                # There are subscribers
                for _worker in self.subscribers_for_results_id[results_id]:
                    self.subscribers_for_results_id[results_id].remove(_worker)
                    _worker.work_if_ready(self.results_for_results_id[results_id])

        # Save results to disk
        if self.model._model_caching_mode == "incremental":
            with open(self.model._cache_file_path, "w") as handle:
                flat_results.to_file(self.model._cache_file_path)
        self.workers_working.remove(worker)

    def _transfer_results(self, worker, flat_results):
        """
        Transfer results and notify observers. Called from workflow.
        """
        results = worker.result_for_path()
        # sets results on workflow
        for path, value in results.items():
            if path in self.observers_for_query.keys():
                for observer in self.observers_for_query[path]:
                    observer.set_consumed_result(path, value)
            flat_results[path] = value

    def _watcher(self, queries, flat_results, shutdown_event):
        """
        Run this watcher on a thread. Runs until all queried data
        is present in the results. Not needed for sequential runs,
        but is necessary when main tread should waiting for
        calculation processes when using multiprocessing
        """
        t_start = time.perf_counter()
        should_stop = False
        while not should_stop and not shutdown_event.is_set():
            _workers_completed = [
                worker for worker in self.workers_working if worker.results_ready()
            ]
            for worker in _workers_completed:
                logging.debug("Query runner detected that a worker completed.")
                self._set_worker_completed(worker, flat_results)

            should_stop = all([query in flat_results.keys() for query in queries])
            time.sleep(POLLTIME)

        elapsed_time = self._add_log_items(t_start)
        logging.info("Response created in {} s".format(elapsed_time))

        # Save results
        if self.model._model_caching_mode == "after_execution":
            flat_results.to_file(self.model._cache_file_path)

    def _add_log_items(self, t_start: float) -> float:
        # Set zeros for all components
        worker_counts = {
            component.id: 0 for component in self.model.model_cfg.components
        }
        worker_counts.update(count(self.workers, key_from="name"))

        # Set zeros for all components
        cache_counts = {
            component.id: 0 for component in self.model.model_cfg.components
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
