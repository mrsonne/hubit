from __future__ import annotations
from typing import Any, Callable, List, Tuple, Dict
from multiprocessing import Manager
import logging
import importlib
import os
import sys
import time
import copy
import itertools
import subprocess
import yaml
from datetime import datetime
from threading import Thread, Event
from .worker import _Worker
from .shared import (
    IDX_WILDCARD,
    LengthTree,
    clean_idxids_from_path,
    convert_to_internal_path,
    idxs_for_matches,
    flatten,
    get_idx_context,
    set_ilocs_on_path,
    idxids_from_path,
    get_iloc_indices,
    inflate,
    set_element,
    is_digit,
    remove_braces_from_path,
    tree_for_idxcontext,
    HubitError,
)
from multiprocessing import Pool, TimeoutError, cpu_count, active_children

from hubit import shared

POLLTIME = 0.1
POLLTIME_LONG = 0.25
THISPATH = os.path.dirname(os.path.realpath(__file__))


def _default_skipfun(value_for_path: Dict) -> bool:
    """
    value_for_path is a flat dict with internal paths as keys
    """
    return False


class HubitModelNoInputError(HubitError):
    def __init__(self):
        self.message = (
            "No input set on the model instance. Set input using the set_input() method"
        )

    def __str__(self):
        return self.message


class HubitModelNoResultsError(HubitError):
    def __init__(self):
        self.message = "No results found on the model instance so cannot reuse results"

    def __str__(self):
        return self.message


class HubitModelComponentError(HubitError):
    pass


class HubitModelValidationError(HubitError):
    def __init__(self, path, fname, fname_for_path):
        fstr = '"{}" on component "{}" also provided by component "{}"'
        self.message = fstr.format(path, fname, fname_for_path[path])

    def __str__(self):
        return self.message


class HubitModelQueryError(HubitError):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


def callback(x):
    # Callback
    logging.debug("WELCOME BACK! WELCOME BACK! WELCOME BACK! WELCOME BACK!")


def _get(
    queryrunner, queries, flat_input, flat_results=None, dryrun=False, expand_iloc=False
):
    """
    With the 'queryrunner' object deploy the queries
    in 'queries'.

    flat_results is a dict and will be modified

    If dryrun=True the workers will generate dummy results. Usefull
    to validate s query.
    """
    # Reset book keeping data
    queryrunner.workers = []
    queryrunner.workers_working = []
    queryrunner.workers_completed = []
    queryrunner.worker_for_id = {}
    queryrunner.observers_for_query = {}

    extracted_input = {}
    tstart = time.time()

    if flat_results is None:
        flat_results = {}

    # Expand the query and get the max ilocs for each query
    queries_for_query = {
        qstr1: queryrunner.model._expand_query(qstr1) for qstr1 in queries
    }
    _queries = [qstr for qstrs in queries_for_query.values() for qstr in qstrs]

    logging.debug(f"Expanded query {queries_for_query}")

    # Start thread that periodically checks whether we are finished or not
    shutdown_event = Event()
    watcher = Thread(
        target=queryrunner._watcher, args=(_queries, flat_results, shutdown_event)
    )
    watcher.daemon = True

    # remeber to send SIGTERM for processes
    # https://stackoverflow.com/questions/11436502/closing-all-threads-with-a-keyboard-interrupt
    the_err = None
    try:
        watcher.start()
        if queryrunner.mpworkers:
            with Manager() as manager:
                success = queryrunner._deploy(
                    manager,
                    _queries,
                    extracted_input,
                    flat_results,
                    flat_input,
                    dryrun=dryrun,
                )
                watcher.join()
        else:
            manager = None
            success = queryrunner._deploy(
                manager,
                _queries,
                extracted_input,
                flat_results,
                flat_input,
                dryrun=dryrun,
            )
            watcher.join()

    except (Exception, KeyboardInterrupt) as err:
        the_err = err
        shutdown_event.set()

    # Join workers
    queryrunner._join_workers()

    if the_err is None:
        # print(flat_results)
        response = {query: flat_results[query] for query in _queries}

        if not expand_iloc:
            # TODO: compression call belongs on model (like expand)
            response = queryrunner.model._compress_response(response, queries_for_query)

        logging.info("Response created in {} s".format(time.time() - tstart))
        return response, flat_results
    else:
        # Re-raise if failed
        raise the_err


class HubitModel:
    def __init__(self, cfg, base_path=os.getcwd(), output_path="./", name="NA"):
        """Initialize a Hubit model

        Args:
            cfg (Dict): Model configuration
            base_path (str, optional): Base path for the model. Defaults to current working directory.
            output_path (str, optional): Output path relative to base_path. Defaults to './'.
            name (str, optional): Model name. Defaults to 'NA'.

        Raises:
            HubitError: [description]
        """

        if os.path.isabs(output_path):
            raise HubitError("Output path should be relative")

        self.ilocstr = "_IDX"
        self.module_for_clsname = {}
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
        self.tree_for_idxcontext = {}

        # Stores trees for query
        self._tree_for_qpath = {}

        # Stores normalized query paths
        self._normqpath_for_qpath = {}

        # Store the model path that matches the query
        self._modelpath_for_querypath = {}

        self.name = name
        self.base_path = base_path
        self.odir = os.path.normpath(os.path.join(self.base_path, output_path))
        self.inputdata = None
        self.flat_input = None
        self.flat_results = None
        self._input_is_set = False

    @classmethod
    def from_file(cls, model_file_path, output_path="./", name=None):
        """Creates a model from file

        Args:
            model_file_path (str): The location of the model file. The model base path will be set to the path of the model file and consequently the model component 'path' attribute should be relative to the model file.
            output_path (str, optional): Path where results should be saved. Defaults to './'.
            name (str, optional): Model name. Defaults to None.

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

    def set_input(self, input_data):
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

    def set_results(self, results_data):
        """
        Set the (hierarchical) results on the model

        Args:
            results_data (Dict): Results data typically in a dict-like format

        Returns:
            HubitModel: Hubit model with input set
        """
        self.flat_results = flatten(results_data)
        return self

    def render(self, queries=[], file_idstr=""):
        """Renders graph representing the model or the query.
        If 'queries' is not provided (or is empty) the model
        is rendered while the query is rendered if 'queries'
        are provided. Rendering the query requires the input data
        has been set.

        Args:
            queries (List, optional): Query path items. Defaults to [].
            file_idstr (str, optional): Identifier appended to the
            image file name.
        """

        dot, filename = self._get_dot(queries, file_idstr)
        filepath = os.path.join(self.odir, filename)
        dot.render(filepath, view=False)
        if os.path.exists(filepath):
            os.remove(filepath)

    def _get_dot(self, queries, file_idstr):
        """
        Construct dot object and get the filename.

        Args:
            See render()
        """
        try:
            from graphviz import Digraph
        except ImportError as err:
            logging.debug(
                'Error: Rendering requires "graphviz", but it could not be imported'
            )
            raise err

        # Some settings
        calc_color = "#F7DC6F"
        calc_dark_color = "#D4AC0D"
        calc_light_color = "#FCF3CF"
        input_color = "#EC7063"
        input_dark_color = "#CB4335"
        input_light_color = "#FADBD8"
        results_color = "#52BE80"
        results_light_color = "#D4EFDF"
        results_dark_color = "#1E8449"
        request_color = "#5499C7"
        request_dark_color = "#1F618D"
        request_light_color = "#D4E6F1"
        calc_shape = "ellipse"
        calc_style = "filled"
        arrowsize = ".5"
        request_shape = "box"
        renderformat = "png"
        fontname = "monospace"
        fontsize_small = "9"

        # strict=True assures that only one edge is drawn although many may be defined
        dot = Digraph(comment="hubit model", format=renderformat, strict=True)
        dot.attr(compound="true", ratio="1.")

        # Get the date and user
        fstr = "Hubit model: {}\nRendered at {} by {}"
        dot.attr(
            label=fstr.format(
                self.name,
                datetime.now().strftime("%b %d %Y %H:%M"),
                subprocess.check_output(["whoami"])
                .decode("ascii", errors="ignore")
                .replace("\\", "/"),
            ),
            fontsize=fontsize_small,
            fontname=fontname,
        )

        if len(queries) > 0:
            # Render a query

            if not self._input_is_set:
                raise HubitModelNoInputError()

            isquery = True
            filename = "query"

            direction = -1

            # Run validation since this returns (dummy) workers
            workers = self._validate_query(queries, mpworkers=False)

            with dot.subgraph(
                name="cluster_request", node_attr={"shape": "box"}
            ) as subgraph:
                subgraph.attr(
                    rank="same",
                    label="User request",
                    fontcolor=request_dark_color,
                    style="filled",
                    fillcolor=request_light_color,
                    color=request_light_color,
                )

                # Make a node for the query
                subgraph.node(
                    name="_Query",
                    label="\n".join(queries),
                    shape=request_shape,
                    color="none",
                    fontsize=fontsize_small,
                    fontname=fontname,
                )
        else:
            # Render a model

            isquery = False
            filename = "model"
            direction = -1
            workers = []
            for component_data in self.cfg:
                func_name = component_data["func_name"]
                path = component_data["provides"][0]["path"]
                dummy_query = convert_to_internal_path(
                    set_ilocs_on_path(path, ["0" for _ in idxids_from_path(path)])
                )

                # Get function and version to init the worker
                (func, version, _) = _QueryRunner._get_func(
                    self.base_path, func_name, component_data, components={}
                )
                manager = None
                workers.append(
                    _Worker(
                        manager,
                        self,
                        func_name,
                        component_data,
                        dummy_query,
                        func,
                        version,
                        self.tree_for_idxcontext,
                    )
                )

        if self.name is not None:
            filename = "{}_{}".format(filename, self.name.lower().replace(" ", "_"))

        if not file_idstr == "":
            filename = "{}_{}".format(filename, file_idstr)

        # Component (calculation) nodes from workers
        with dot.subgraph(name="cluster_calcs", node_attr={"shape": "box"}) as subgraph:
            subgraph.attr(
                rank="same",
                label="Calculations",
                fontcolor=calc_dark_color,
                style="filled",
                fillcolor=calc_light_color,
                color=calc_light_color,
            )

            for w in workers:
                subgraph.node(
                    name=w.name,  # Name identifier of the node
                    label=w.name + "\nv {}".format(w.version),
                    fontname=fontname,
                    shape=calc_shape,
                    style=calc_style,
                    fillcolor=calc_color,
                    color=calc_color,
                    fontsize=fontsize_small,
                )

        # Extract object names to allow pointing to e.g. results cluster.
        # This requires one node id in the cluster
        prefix_results = "cluster_results"
        prefix_input = "cluster_input"

        (input_object_ids, results_object_ids) = self._get_binding_ids(
            prefix_input, prefix_results
        )

        if isquery:
            # Draw edge from the query to the results
            dot.edge(
                "_Query",
                results_object_ids[0],  # some node in subgraph
                lhead=prefix_results,  # anchor head at subgraph edge
                ltail="cluster_request",  # anchor head at subgraph edge
                label="query",
                fontsize=fontsize_small,
                fontcolor=request_color,
                fontname=fontname,
                constraint="false",
                arrowsize=arrowsize,
                color=request_color,
            )

            dot.edge(
                results_object_ids[0],  # some node in subgraph
                "_Query",
                ltail=prefix_results,  # anchor head at subgraph edge
                lhead="cluster_request",  # anchor head at subgraph edge
                label="response",
                fontsize=fontsize_small,
                fontcolor=request_color,
                fontname=fontname,
                constraint="false",
                arrowsize=arrowsize,
                color=request_color,
            )

        for w in workers:
            with dot.subgraph(
                name="cluster_input", node_attr={"shape": "box"}
            ) as subgraph:
                subgraph.attr(
                    label="Input data",
                    color=input_light_color,
                    fillcolor=input_light_color,
                    fontcolor=input_dark_color,
                    style="filled",
                )
                self._render_objects(
                    w.name,
                    w.mpath_for_name("input"),
                    "cluster_input",
                    prefix_input,
                    input_object_ids[0],
                    subgraph,
                    arrowsize,
                    fontsize_small,
                    fontname,
                    input_color,
                    direction=-direction,
                )

            with dot.subgraph(
                name="cluster_results", node_attr={"shape": "box"}
            ) as subgraph:

                subgraph.attr(
                    label="Results data",
                    labelloc="b",  # place at the bottom
                    color=results_light_color,
                    fillcolor=results_light_color,
                    fontcolor=results_dark_color,
                    style="filled",
                )

                self._render_objects(
                    w.name,
                    w.mpath_for_name("provides"),
                    "cluster_results",
                    prefix_results,
                    results_object_ids[0],
                    subgraph,
                    arrowsize,
                    fontsize_small,
                    fontname,
                    results_color,
                    direction=direction,
                )

                # Not all components cosume results
                try:
                    self._render_objects(
                        w.name,
                        w.mpath_for_name("results"),
                        "cluster_results",
                        prefix_results,
                        results_object_ids[0],
                        subgraph,
                        arrowsize,
                        fontsize_small,
                        fontname,
                        results_color,
                        direction=-direction,
                        constraint="false",
                        render_objects=False,
                    )
                except KeyError:
                    pass

        return dot, filename

    @staticmethod
    def _add_object_for_index(
        idx, dot, prefix, pathcmps, pathcmps_old, idxids, color, fontsize, fontname
    ):
        path_component = pathcmps[idx]
        peripheries = "1"
        is_list = False
        # check the next component in the original pathstr (doesnt work for repeated keys)
        try:
            # Check if the path component after the current indicates a list
            pcmp_old = pathcmps_old[pathcmps_old.index(path_component) + 1]
            if IDX_WILDCARD in pcmp_old or pcmp_old in idxids:
                peripheries = "1"  # use multiple outlines to indicate lists
                is_list = True
        except IndexError:
            pass

        _id = f"{prefix}_{path_component}"

        dot.node(
            _id,
            path_component + (" ☰" if is_list else ""),
            shape="parallelogram",
            color=color,
            fillcolor=color,
            style="filled",
            fontsize=fontsize,
            fontname=fontname,
            peripheries=peripheries,
        )
        return _id, is_list

    def _render_objects(
        self,
        fun_name,
        cdata,
        clusterid,
        prefix,
        cluster_node_id,
        dot,
        arrowsize,
        fontsize,
        fontname,
        color,
        direction=1,
        constraint="true",
        render_objects=True,
    ):
        """
        The constraint attribute, which lets you add edges which are
        visible but don't affect layout.
        https://stackoverflow.com/questions/2476575/how-to-control-node-placement-in-graphviz-i-e-avoid-edge-crossings

        # TODO: this function needs cleaning
        """

        def get_attr_map(name, path, attr_name, direction, use_path=True):
            if direction == 1:
                attr_map = f"{path} ➔ {name}" if use_path else f"{attr_name} ➔ {name}"
            else:
                # if we are on the results end start with internal components name and map to data model name
                attr_map = f"{name} ➔ {path}" if use_path else f"{name} ➔ {attr_name}"
            return attr_map

        ids = []
        skipped = []
        label_for_edgeid = {}
        for name, path in cdata.items():
            idxids = clean_idxids_from_path(path)

            # Path components with braces and index specifiers
            pathcmps_old = convert_to_internal_path(path).split(".")

            # Path components with node names only
            pathcmps = remove_braces_from_path(path).split(".")

            # Collect data for connecting to nearest objects
            # and labeling the edge with the attributes consumed/provided
            if len(pathcmps) > 1:
                should_skip = False
                data_node_id = f"{prefix}_{pathcmps[-2]}"
                data_to_fun_edge_id = data_node_id, fun_name
                attr_map = get_attr_map(name, path, pathcmps[-1], direction)

                try:
                    label_for_edgeid[data_to_fun_edge_id].append(attr_map)
                except KeyError:
                    label_for_edgeid[data_to_fun_edge_id] = [attr_map]
            else:
                # If not nested save it and skip
                should_skip = True
                skipped.append(pathcmps[0])

            if not should_skip and render_objects:

                # Add and connect objects
                nobjs = len(pathcmps) - 1
                for idx in range(nobjs):

                    # Add node for objetc at idx and get back the id
                    _id, is_list = HubitModel._add_object_for_index(
                        idx,
                        dot,
                        prefix,
                        pathcmps,
                        pathcmps_old,
                        idxids,
                        color,
                        fontsize,
                        fontname,
                    )

                    # exclude bottom-most level (attributes)
                    if idx >= nobjs - 1:
                        continue

                    # Add node for objetc at idx + 1 and get back the id
                    _id_next, is_list_next = HubitModel._add_object_for_index(
                        idx + 1,
                        dot,
                        prefix,
                        pathcmps,
                        pathcmps_old,
                        idxids,
                        color,
                        fontsize,
                        fontname,
                    )

                    ids.extend([_id, _id_next])

                    # Connect current object with next
                    dot.edge(
                        _id,
                        _id_next,
                        taillabel="1 ",
                        headlabel="* "
                        if is_list_next
                        else "1 ",  # add space between label and edge
                        fontsize=fontsize,
                        arrowsize=str(float(arrowsize) * 1.5),
                        color=color,
                        constraint=constraint,
                        arrowhead="none",
                        arrowtail="diamond",
                        dir="both",
                    )

        # Connect data objects with calculations with consumes attributes on edges
        HubitModel._edge_with_label(
            label_for_edgeid, color, constraint, direction, arrowsize, dot
        )

        # Render nodes that were skipped since they are not connected to other data nodes
        if len(skipped) > 0:
            if direction == 1:
                clusterid_tail = clusterid
                clusterid_head = None
            else:
                clusterid_tail = None
                clusterid_head = clusterid

            label_for_edgeid = {(cluster_node_id, fun_name): skipped}
            HubitModel._edge_with_label(
                label_for_edgeid,
                color,
                constraint,
                direction,
                arrowsize,
                dot,
                ltail=clusterid_tail,
                lhead=clusterid_head,
            )

        return skipped, ids

    def _get_binding_ids(self, prefix_input, prefix_results):
        """
        Get list of objects from model that need redering e.g. layers and segment.
        These object name are prefixed to cluster them
        """
        results_object_ids = set()
        input_object_ids = set()
        for component in self.cfg:
            binding = component["provides"]
            results_object_ids.update(
                [
                    "{}_{}".format(prefix_results, objname)
                    for objname in self._get_path_cmps(binding)
                ]
            )

            binding = component["consumes"]["input"]
            input_object_ids.update(
                [
                    "{}_{}".format(prefix_input, objname)
                    for objname in self._get_path_cmps(binding)
                ]
            )

            # Not all components consume results
            try:
                binding = component["consumes"]["results"]
                results_object_ids.update(
                    [
                        "{}_{}".format(prefix_results, objname)
                        for objname in self._get_path_cmps(binding)
                    ]
                )
            except KeyError:
                pass

        results_object_ids = list(results_object_ids)
        input_object_ids = list(input_object_ids)
        return input_object_ids, results_object_ids

    # def _cleanpathcmps(self, pathcmps):
    #     print('XXXX', pathcmps)
    #     # TODO: check for digits and mark box below

    #     _pathcmps = copy.copy(pathcmps)
    #     try:
    #         _pathcmps.remove(self.ilocstr)
    #     except ValueError:
    #         pass

    #     try:
    #         _pathcmps.remove(IDX_WILDCARD)
    #     except ValueError:
    #         pass

    #     _pathcmps = [cmp
    #                  for cmp in _pathcmps
    #                  if not is_digit(cmp)]

    #     return _pathcmps

    def _get_path_cmps(self, bindings):
        """
        Get path components from binding data
        """
        cmps = set()
        for binding in bindings:
            pathcmps = remove_braces_from_path(binding["path"]).split(".")
            # pathcmps = self._cleanpathcmps( binding['path'].split(".") )
            if len(pathcmps) - 1 > 0:
                cmps.update(pathcmps[:-1])
        return cmps

    @staticmethod
    def _edge_with_label(
        names_for_nodeids,
        color,
        constraint,
        direction,
        arrowsize,
        dot,
        ltail=None,
        lhead=None,
    ):
        # Render attributes consumed/provided
        # Add space on the right side of the label. The graph becomes
        # wider and the edge associated with a given label becomes clearer
        spaces = 7
        fstr = '<tr><td align="left">{}</td><td>{}</td></tr>'
        for t, attrnames in names_for_nodeids.items():
            tmp = "".join(
                [fstr.format(attrname, " " * spaces) for attrname in attrnames]
            )

            labelstr = f'<<table cellpadding="0" border="0" cellborder="0">\
                        {tmp}\
                        </table>>'

            # ltail is there to attach attributes directly on the cluster
            dot.edge(
                *t[::direction],
                label=labelstr,
                ltail=ltail,
                lhead=lhead,
                fontsize="9",
                fontname="monospace",
                fontcolor=color,
                color=color,
                arrowsize=arrowsize,
                arrowhead="vee",
                labeljust="l",
                constraint=constraint,
            )

    def get_results(self, flat=False):
        if flat:
            return self.flat_results
        else:
            return inflate(self.flat_results)

    def get(self, queries, mpworkers=False, validate=False, reuse_results=False):
        """Generate respose corresponding to the 'queries'

        Args:
            queries ([List]): Query path items
            mpworkers (bool, optional): Flag indicating if the respose should be generated using (async) multiprocessing. Defaults to False.
            validate (bool, optional): Flag indicating if the query should be validated prior to execution. Defaults to False.

        Raises:
            HubitModelNoInputError: If no input is set on the model

        Returns:
            [Dict]: The response
        """
        if not self._input_is_set:
            raise HubitModelNoInputError()

        if reuse_results and self.flat_results is None:
            raise HubitModelNoResultsError()

        # Make a query runner
        qrunner = _QueryRunner(self, mpworkers)

        if validate:
            _get(qrunner, queries, self.flat_input, dryrun=True)

        if reuse_results:
            _flat_results = self.flat_results
        else:
            _flat_results = {}

        response, self.flat_results = _get(
            qrunner, queries, self.flat_input, _flat_results
        )
        return response

    def _set_trees(self):
        """Compute and set trees for all index contexts in model"""
        self.tree_for_idxcontext = tree_for_idxcontext(
            self.component_for_name.values(), self.inputdata
        )

    def _validate_query(self, queries, mpworkers=False):
        """
        Run the query using a dummy calculation to see that all required
        input and results are available
        """
        qrunner = _QueryRunner(self, mpworkers)
        _get(qrunner, queries, self.flat_input, dryrun=True)
        return qrunner.workers

    def _validate_model(self):
        fname_for_path = {}
        for compdata in self.cfg:
            fname = compdata["func_name"]
            for binding in compdata["provides"]:
                if not binding["path"] in fname_for_path:
                    fname_for_path[binding["path"]] = fname
                else:
                    raise HubitModelValidationError(
                        binding["path"], fname, fname_for_path
                    )

    def get_many(
        self,
        queries: List[str],
        input_values_for_path: Dict,
        skipfun: Callable[[Dict], bool] = _default_skipfun,
        nproc: Any = None,
    ) -> Tuple:
        """Will perform a full factorial sampling of the
        input points specified in 'input_values_for_path'.

        Note that on windows calling get_many should be guarded by
        if __name__ == '__main__':

        Args:
            queries (List): Query path items
            input_values_for_path (Dict): Dictionary with keys representing path items. The corresponding values should be an iterable with elements representing discrete values for the attribute at the path.
            skipfun (Callable): If returns True the factor combination is skipped
            nproc (int, optional): Number of processes to use. Defaults to None. If not specified a suitable default is used.

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
            qrun = _QueryRunner(self, mpworkers=False)
            flat_results = {}
            args.append((qrun, queries, _flat_input, flat_results))
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

        logging.info("Queries processed in {} s".format(time.time() - tstart))

        # TODO convert inps to external paths
        return responses, inps, results

    # def plot(self, inps, responses):
    #     """
    #     TODO: implement parallel coordinates plot
    #     https://stackoverflow.com/questions/8230638/parallel-coordinates-plot-in-matplotlib
    #     """
    #     pass

    def validate(self, queries=[]):
        """
        Validate a model or query. Will validate as a query if
        queries are provided.

        The model validation checks that there are
            - not multiple components providing the same attribute

        The query validation checks that
            - all required input are available
            - all required results are provided

        Args:
            queries (List, optional): Query path items. Defaults to [].

        Returns:
            True if validation was successful

        TODO: check for circular references,
              check that ] is followed by . in paths
              check that if X in [X] contains : then it should be followed by @str
              Component that consumes a specified index ID should also provide a result at the same location in the results data model. Not necesary if all indices (:) are consumed. I.e. the provider path should contain all index info
        """
        if len(queries) > 0:
            if not self._input_is_set:
                raise HubitModelNoInputError()
            self._validate_query(queries, mpworkers=False)
        else:
            self._validate_model()

        return True

    def _cmpnames_for_query(self, qpath: str):
        """
        Find names of components that can respond to the "query".
        """
        # TODO: Next two lines should only be executed once in init (speed)
        itempairs = [
            (cmpdata["func_name"], bindings["path"])
            for cmpdata in self.cfg
            for bindings in cmpdata["provides"]
        ]
        func_names, providerstrings = zip(*itempairs)
        return [func_names[idx] for idx in idxs_for_matches(qpath, providerstrings)]

    def _cmpname_for_query(self, path: str):
        """Find name of component that can respond to the "query".

        Args:
            path (str): Query path

        Raises:
            HubitModelQueryError: Raised if no or multiple components provide the
            queried attribute

        Returns:
            str: Function name
        """
        # Get all components that provide data for the query
        func_names = self._cmpnames_for_query(path)

        if len(func_names) > 1:
            fstr = "Fatal error. Multiple providers for query '{}': {}"
            msg = fstr.format(path, func_names)
            raise HubitModelQueryError(msg)

        if len(func_names) == 0:
            msg = f"Fatal error. No provider for query path '{path}'."
            raise HubitModelQueryError(msg)

        # Get the provider function for the query
        return func_names[0]

    def mpath_for_qpath(self, qpath: str) -> str:
        # Find component that provides queried result
        cmp_name = self._cmpname_for_query(qpath)

        # Find and prune tree
        cmp = self.component_for_name[cmp_name]
        idx = idxs_for_matches(qpath, [binding["path"] for binding in cmp["provides"]])[
            0
        ]
        return cmp["provides"][idx]["path"]

    def _expand_query(self, qpath: str) -> List[str]:
        """
        Expand query so that any index wildcards are converte to
        real indies

        TODO: NEgative indices... prune_tree requires real indices but normalize
        path require all IDX_WILDCARDs be expanded to get the context

        # TODO: Save pruned trees so the worker need not prune top level trees again
        # TODO: save component so we dont have to find top level components again
        """
        mpath = self.mpath_for_qpath(qpath)
        self._modelpath_for_querypath[qpath] = mpath
        idxcontext = get_idx_context(mpath)
        tree = self.tree_for_idxcontext[idxcontext]
        # qpath_normalized = tree.normalize_path(qpath)
        pruned_tree = tree.prune_from_path(
            convert_to_internal_path(qpath),
            convert_to_internal_path(mpath),
            inplace=False,
        )
        # Store tree
        self._tree_for_qpath[qpath] = pruned_tree

        # Store normalized paths
        # self._normqpath_for_qpath[qpath] = qpath_normalized

        # Expand the path
        return pruned_tree.expand_path(
            qpath, flat=True, path_type="query", as_internal_path=True
        )

    def _compress_response(self, response, queries_for_query):
        """
        Compress the response to reflect queries with index wildcards.
        So if the query has the structure list1[:].list2[:] and is
        rectangular with N1 (2) elements in list1 and N2 (3) elements
        in list2 the compressed response will be a nested list like
        [[00, 01, 02], [10, 11, 12]]
        """
        _response = {}
        for qpath_org, qpaths_expanded in queries_for_query.items():
            if (
                qpaths_expanded[0]
                == convert_to_internal_path(qpath_org)
                # or
                # qpaths_expanded[0] == convert_to_internal_path( self._normqpath_for_qpath[qpath_org] )
            ):
                _response[qpath_org] = response[qpaths_expanded[0]]
            else:
                # Get the index IDs from the original query
                idxids = idxids_from_path(qpath_org)

                # Get pruned tree
                tree = self._tree_for_qpath[qpath_org]
                # Initialize list to collect all iloc indices for each wildcard
                values = tree.none_like()

                # Extract iloc indices for each query in the expanded query
                for qpath in qpaths_expanded:
                    mpath = convert_to_internal_path(
                        self._modelpath_for_querypath[qpath_org]
                    )
                    ilocs = get_iloc_indices(qpath, mpath, tree.level_names)
                    # Only keep ilocs that come from an expansion... otherwise
                    # the dimensions of "values" do no match
                    ilocs = [
                        iloc
                        for iloc, idxid in zip(ilocs, idxids)
                        if idxid == IDX_WILDCARD
                    ]
                    values = set_element(
                        values, response[qpath], [int(iloc) for iloc in ilocs]
                    )
                _response[qpath_org] = values

        return _response


class _QueryRunner:
    def __init__(self, model, mpworkers):
        """Internal class managing workers. Is in a model, the query runner
        is responsible for deploying and book keeping workers acording
        to a query specified to the model.

        Args:
            model (HubitModel): The model to manage
            mpworkers (bool): Flag indicating if multi-processing should be used
        """
        self.model = model
        self.mpworkers = mpworkers
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
