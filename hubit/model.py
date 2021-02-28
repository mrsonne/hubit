from __future__ import annotations
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
    convert_to_internal_path,
    flatten,
    inflate,
)

from .errors import (
    HubitError,
    HubitModelNoInputError,
    HubitModelNoResultsError,
)


class HubitModel(_HubitModel):
    def __init__(
        self,
        cfg: List[Dict[str, Any]],
        base_path: str = os.getcwd(),
        output_path: str = "./",
        name: str = "NA",
    ):
        """Initialize a Hubit model

        Args:
            cfg (List): Model configuration
            base_path (str, optional): Base path for the model. Defaults to current working directory.
            output_path (str, optional): Output path relative to base_path. Defaults to './'.
            name (str, optional): Model name. Defaults to 'NA'.

        Raises:
            HubitError: If output_path is an absolute path or if components function names are not unique.
        """

        if os.path.isabs(output_path):
            raise HubitError("Output path should be relative")

        self.ilocstr = "_IDX"
        self.cfg = cfg

        fnames = [component["func_name"] for component in cfg]

        if not len(fnames) == len(set(fnames)):
            raise HubitError("Component function names must be unique")

        self.component_for_name = {
            component["func_name"]: component for component in cfg
        }

        # Insert empty if section if missing
        for component in self.component_for_name.values():
            if not "consumes" in component:
                component["consumes"] = {}

            if not "input" in component["consumes"]:
                component["consumes"]["input"] = {}

        # Stores length tree. Filled when set_input() is called
        self.tree_for_idxcontext: Dict[LengthTree, str] = {}

        # Stores trees for query
        self._tree_for_qpath: Dict[LengthTree, str] = {}

        # Stores normalized query paths
        self._normqpath_for_qpath: Dict[str, str] = {}

        # Store the model path that matches the query
        self._modelpath_for_querypath: Dict[str, str] = {}

        self.name = name
        self.base_path = base_path
        self.odir = os.path.normpath(os.path.join(self.base_path, output_path))
        self.inputdata: Dict[str, Any] = {}
        self.flat_input: Dict[str, Any] = {}
        self.flat_results: Dict[str, Any] = {}
        self._input_is_set = False

    @classmethod
    def from_file(
        cls, model_file_path: str, output_path: str = "./", name: str = "NA"
    ) -> HubitModel:
        """Creates a model from file

        Args:
            model_file_path (str): The location of the model file. The model base path will be set to the path of the model file and consequently the model component 'path' attribute should be relative to the model file.
            output_path (str, optional): Path where results should be saved. Defaults to './'.
            name (str, optional): Model name. Defaults to "NA".

        Returns:
            HubitModel: Hubit model object as defined in the specified model file
        """
        with open(model_file_path, "r") as stream:
            components = yaml.load(stream, Loader=yaml.FullLoader)

        # Convert to absolute paths
        base_path = os.path.dirname(model_file_path)
        for component in components:
            if "path" in component.keys():
                component["path"] = os.path.abspath(
                    os.path.join(base_path, component["path"])
                )
        return cls(components, name=name, output_path=output_path, base_path=base_path)

    def set_input(self, input_data: Dict[str, Any]) -> HubitModel:
        """
        Set the (hierarchical) input on the model

        Args:
            input_data (Dict): Input data typically in a dict-like format

        Returns:
            HubitModel: Hubit model with input set
        """
        self.inputdata = input_data
        self.flat_input = flatten(input_data)
        self._set_trees()
        self._input_is_set = True
        return self

    def set_results(self, results_data: Dict[str, Any]) -> HubitModel:
        """
        Set the (hierarchical) results on the model

        Args:
            results_data (Dict): Results data typically in a nested dict-like format

        Returns:
            HubitModel: Hubit model with input set
        """
        self.flat_results = flatten(results_data)
        return self

    def render(self, query: List[str] = [], file_idstr: str = "") -> None:
        """Renders graph representing the model or the query.
        If 'query' is not provided (or is empty) the model
        is rendered while the query is rendered if 'query'
        are provided. Rendering the query requires the input data
        has been set.

        Args:
            query (List, optional): Query paths. Defaults to [].
            file_idstr (str, optional): Identifier appended to the
            image file name.
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
            flat (bool, optional): If True the results will be returned as a flat dict. Otherwise the returned results object is a nested dict. Defaults to False.

        Returns:
            Dict: Results object
        """
        if flat:
            return self.flat_results
        else:
            return inflate(self.flat_results)

    def get(
        self,
        query,
        use_multi_processing: bool = False,
        validate: bool = False,
        reuse_results: bool = False,
    ) -> Dict[str, Any]:
        """Generate respose corresponding to the 'query'

        Args:
            query ([List]): Query paths
            use_multi_processing (bool, optional): Flag indicating if the respose should be generated using (async) multiprocessing. Defaults to False.
            validate (bool, optional): Flag indicating if the query should be validated prior to execution. Defaults to False.
            reuse_results (bool, optional). If True, results already set on the model will be used as-is i.e. not recalculated. Defaults to False.

        Raises:
            HubitModelNoInputError: If no input is set on the model

        Returns:
            Dict: The response
        """
        if not self._input_is_set:
            raise HubitModelNoInputError()

        if reuse_results and self.flat_results is None:
            raise HubitModelNoResultsError()

        # Make a query runner
        qrunner = _QueryRunner(self, use_multi_processing)

        if validate:
            _get(qrunner, query, self.flat_input, dryrun=True)

        if reuse_results:
            _flat_results = self.flat_results
        else:
            _flat_results = {}

        response, self.flat_results = _get(
            qrunner, query, self.flat_input, _flat_results
        )
        return response

    def get_many(
        self,
        query: List[str],
        input_values_for_path: Dict[str, Any],
        skipfun: Callable[[Dict[str, Any]], bool] = default_skipfun,
        nproc: Any = None,
    ) -> Tuple:
        """Will perform a full factorial sampling of the
        input points specified in 'input_values_for_path'.

        Note that on windows calling get_many should be guarded by
        if __name__ == '__main__':

        Args:
            query (List): Query paths
            input_values_for_path (Dict): Dictionary with keys representing path items. The corresponding values should be an iterable with elements representing discrete values for the attribute at the path.
            skipfun (Callable): If returns True the factor combination is skipped
            nproc (Any, optional): Number of processes to use. Defaults to None in which case a suitable default is used.

        Raises:
            HubitModelNoInputError: [description]

        Returns:
            Tuple: 3-tuple with a list of responses in the element 0, a list of the
            corresponding inputs in element 1 and a list of the results in element 2.
        """
        if not self._input_is_set:
            raise HubitModelNoInputError()

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
                _flat_input[convert_to_internal_path(path)] = val

            if skipfun(_flat_input):
                continue
            qrun = _QueryRunner(self, use_multi_processing=False)
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

        The model validation checks that there are
            - not multiple components providing the same attribute

        The query validation checks that
            - all required input are available
            - all required results are provided

        Args:
            query (List, optional): Query paths. Defaults to [].

        Raises:
            HubitModelNoInputError: If not input is set.
            HubitModelValidationError: If validation fails

        Returns:
            True if validation was successful. If not successful a HubitModelValidationError is raised

        TODO: check for circular references,
              check that ] is followed by . in paths
              check that if X in [X] contains : then it should be followed by @str
              Component that consumes a specified index ID should also provide a result at the same location in the results data model. Not necesary if all indices (:) are consumed. I.e. the provider path should contain all index info
        """
        if len(query) > 0:
            if not self._input_is_set:
                raise HubitModelNoInputError()
            self._validate_query(query, use_multi_processing=False)
        else:
            self._validate_model()

        return True
