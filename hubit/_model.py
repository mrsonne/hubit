from __future__ import annotations
from typing import List, Dict, Any
from multiprocessing import Manager
import logging
import os
import time
import subprocess
from datetime import datetime
from threading import Thread, Event

from .worker import _Worker
from .qrun import _QueryRunner
from .shared import (
    IDX_WILDCARD,
    clean_idxids_from_path,
    convert_to_internal_path,
    idxs_for_matches,
    get_idx_context,
    set_ilocs_on_path,
    idxids_from_path,
    get_iloc_indices,
    set_element,
    remove_braces_from_path,
    tree_for_idxcontext,
)

from .errors import (
    HubitModelNoInputError,
    HubitModelValidationError,
    HubitModelQueryError,
)

THISPATH = os.path.dirname(os.path.realpath(__file__))


def default_skipfun(_: Dict[str, Any]) -> bool:
    """
    value_for_path is a flat dict with internal paths as keys
    """
    return False


def _get(
    queryrunner, query, flat_input, flat_results=None, dryrun=False, expand_iloc=False
):
    """
    With the 'queryrunner' object deploy the paths
    in 'query'.

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
        qstr1: queryrunner.model._expand_query(qstr1) for qstr1 in query
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
        if queryrunner.use_multi_processing:
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


class _HubitModel:
    """
    Contains all private methods and should not be used. Use the public version model.HubitModel
    """

    def __init__(self):
        pass

    def _get_dot(self, queries: List[str], file_idstr: str):
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
            workers = self._validate_query(queries, use_multi_processing=False)

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
                    _id, is_list = _HubitModel._add_object_for_index(
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
                    _id_next, is_list_next = _HubitModel._add_object_for_index(
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
        _HubitModel._edge_with_label(
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
            _HubitModel._edge_with_label(
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

    def _set_trees(self):
        """Compute and set trees for all index contexts in model"""
        self.tree_for_idxcontext = tree_for_idxcontext(
            self.component_for_name.values(), self.inputdata
        )

    def _validate_query(self, queries, use_multi_processing=False):
        """
        Run the query using a dummy calculation to see that all required
        input and results are available
        """
        qrunner = _QueryRunner(self, use_multi_processing)
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
