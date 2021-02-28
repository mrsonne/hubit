import copy
import importlib
import logging
import os
import sys
import time
from typing import Any

from .worker import _Worker
from .errors import HubitModelComponentError

POLLTIME = 0.1
POLLTIME_LONG = 0.25


class _QueryRunner:
    def __init__(self, model, use_multi_processing):
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

        # For book-keeping what has already been imported
        self._components = {}

    def _join_workers(self):
        # TODO Not sure this is required
        for i, worker in enumerate(self.workers_completed):
            # https://stackoverflow.com/questions/25455462/share-list-between-process-in-python-server
            worker.join()

    @staticmethod
    def _get_func(base_path, func_name, cfgdata, components):
        """[summary]

        Args:
            base_path (str): Model base path
            func_name (str): Function name
            cfgdata (dict): configuration data from the model definition file

        Returns:
            tuple: function handle, function version, and component dict
        """
        if "path" in cfgdata and "module" in cfgdata:
            raise HubitModelComponentError(
                f'Please specify either "module" '
                f'or "path" for component with '
                f'func_name "{func_name}"'
            )

        if "path" in cfgdata:
            path, file_name = os.path.split(cfgdata["path"])
            path = os.path.join(base_path, path)
            module_name = os.path.splitext(file_name)[0]
            path = os.path.abspath(path)
            file_path = os.path.join(path, file_name)
            component_id = os.path.join(path, func_name)
            if component_id in components.keys():
                func, version = components[component_id]
                return func, version, components

            sys.path.insert(0, path)
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        elif "module" in cfgdata:
            module = importlib.import_module(cfgdata["module"])
            component_id = f'{cfgdata["module"]}{func_name}'
            if component_id in components.keys():
                func, version = components[component_id]
                return func, version, components
        else:
            raise HubitModelComponentError(
                f'Please specify either "module" '
                f'or "path" for component with '
                f'func_name "{func_name}"'
            )

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

        func_name = self.model._cmpname_for_query(query_path)

        component_data = self.model.component_for_name[func_name]
        (func, version, self._components) = _QueryRunner._get_func(
            self.model.base_path, func_name, component_data, self._components
        )

        # Create and return worker
        try:
            return _Worker(
                manager,
                self,
                func_name,
                component_data,
                query_path,
                func,
                version,
                self.model.tree_for_idxcontext,
                dryrun=dryrun,
            )
        except RuntimeError:
            return None

    def _transfer_input(self, input_paths, worker, inputdata, all_input):
        """
        Transfer required input from all input to extracted input
        """
        for path in input_paths:
            val = all_input[path]
            inputdata[path] = val
            worker.set_consumed_input(path, val)

    def _deploy(
        self,
        manager,
        qpaths,
        extracted_input,
        flat_results,
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
            if qpath in flat_results:
                continue

            # Figure out which component can provide a response to the query
            # and get the corresponding worker
            worker = self._worker_for_query(manager, qpath, dryrun=dryrun)
            # if worker is None: return False

            # Skip if the queried data will be provided
            _skip_paths.extend(worker.paths_provided())

            # Check that another query did not already request this worker
            if worker._id in self.worker_for_id.keys():
                continue

            self.worker_for_id[worker._id] = worker

            # Set available data on the worker. If data is missing the corresponding
            # paths (queries) are returned
            (input_paths_missing, queries_next) = worker.set_values(
                extracted_input, flat_results
            )

            self._transfer_input(
                input_paths_missing, worker, extracted_input, all_input
            )

            # Expand requirement paths returned when the worker was filled
            # with input that is currently available
            qpaths_next = [
                qstrexp
                for qstr in queries_next
                for qstrexp in self.model._expand_query(qstr)
            ]
            logging.debug("qpaths_next: {}".format(qpaths_next))

            # Add the worker to the oberservers list for that query in order
            for path_next in qpaths_next:
                if path_next in self.observers_for_query.keys():
                    self.observers_for_query[path_next].append(worker)
                else:
                    self.observers_for_query[path_next] = [worker]

            # Deploy workers for the dependencies
            success = self._deploy(
                manager,
                queries_next,
                extracted_input,
                flat_results,
                all_input,
                skip_paths=_skip_paths,
                dryrun=dryrun,
            )
            # if not success: return False

        return True

    def _set_worker(self, worker):
        """
        Called from _Worker object when the input is set.
        Not on init since we do not yet know if a similar
        object exists.
        """
        self.workers.append(worker)

    def _set_worker_working(self, worker):
        """
        Called from _Worker object just before the worker
        process is started.
        """
        self.workers_working.append(worker)

    def _set_worker_completed(self, worker, all_results):
        """
        Called when results attribute has been populated
        """
        self.workers_completed.append(worker)
        self._transfer_results(worker, all_results)
        self.workers_working.remove(worker)

    def _transfer_results(self, worker, all_results):
        """
        Transfer results and notify observers. Called from workflow.
        """
        results = worker.result_for_path()
        # sets results on workflow
        for path, value in results.items():
            if path in self.observers_for_query.keys():
                for observer in self.observers_for_query[path]:
                    observer.set_consumed_result(path, value)
            all_results[path] = value

    def _watcher(self, queries, flat_results, shutdown_event):
        """
        Run this watcher on a thread. Runs until all queried data
        is present in the results. Not needed for sequential runs,
        but is necessary when main tread should waiting for
        calculation processes when using multiprocessing
        """
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
