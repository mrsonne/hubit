from __future__ import annotations
from typing import List, Dict, Any
import pickle
import hashlib
from multiprocessing import Manager
import logging
import subprocess
from datetime import datetime
from threading import Thread, Event

from .worker import _Worker
from .qrun import _QueryRunner
from .config import (
    FlatData,
    HubitBinding,
    _HubitPath,
    HubitQueryPath,
    Query,
)
from .shared import (
    _QueryExpansion,
    IDX_WILDCARD,
    idxs_for_matches,
    set_element,
    tree_for_idxcontext,
)

from .errors import (
    HubitModelNoInputError,
    HubitModelValidationError,
    HubitModelQueryError,
)


def _default_skipfun(flat_input: FlatData) -> bool:
    """
    flat_input is the input for one factor combination in a sweep
    calculation
    """
    return False


def _get(
    queryrunner,
    query: Query,
    flat_input,
    flat_results: FlatData = FlatData(),
    dryrun: bool = False,
    expand_iloc: bool = False,
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

    # Expand the query for each path
    queries_exp = [queryrunner.model._expand_query(qpath) for qpath in query.paths]
    # Make flat list of expanded queries
    _queries = [qpath for qexp in queries_exp for qpath in qexp.flat_expanded_paths()]

    for qexp in queries_exp:
        logging.debug(f"Expanded query {qexp}")

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
                queryrunner.spawn_workers(
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
            queryrunner.spawn_workers(
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
            response = queryrunner.model._compress_response(response, queries_exp)

        return response, flat_results
    else:
        # Re-raise if failed
        raise the_err


class _HubitModel:
    """
    Contains all private methods and should not be used. Use the public version model.HubitModel
    """

    _valid_model_caching_modes = "none", "incremental", "after_execution"
    _do_model_caching = "incremental", "after_execution"

    def __init__(self):
        pass

    @property
    def base_path(self):
        return self.model_cfg.base_path

    def _add_log_items(
        self,
        worker_counts: Dict[str, int],
        elapsed_time: List[float],
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

    def _get_dot(self, query: Query, file_idstr: str):
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

        if len(query.paths) > 0:
            # Render a query

            if not self._input_is_set:
                raise HubitModelNoInputError()

            isquery = True
            filename = "query"

            direction = -1

            # Run validation since this returns (dummy) workers
            workers = self._validate_query(query, use_multi_processing=False)

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
                    label="\n".join(query.paths),
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
            for component in self.model_cfg.components:
                path = component.provides_results[0].path
                dummy_query = HubitQueryPath(
                    path.set_indices(["0" for _ in path.get_index_specifiers()], mode=1)
                )

                # Get function and version to init the worker
                (func, version, _) = _QueryRunner._get_func(
                    self.base_path, component, components={}
                )
                manager = None
                workers.append(
                    _Worker(
                        manager,
                        self,
                        component,
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
                    w.binding_map("consumes_input"),
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
                    w.binding_map("provides_results"),
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
                        w.binding_map("consumes_results"),
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
            idxids = path.get_index_identifiers()

            # Path components with braces and index specifiers
            pathcmps_old = _HubitPath.as_internal(path).split(".")

            # Path components with node names only
            pathcmps = path.remove_braces().split(".")

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

    def _get_path_cmps(self, bindings: HubitBinding):
        """
        Get path components from bindings
        """
        cmps = set()
        for binding in bindings:
            pathcmps = binding.path.remove_braces().split(".")
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
            self.model_cfg.component_for_id.values(), self.inputdata
        )

    def _validate_query(self, query: Query, use_multi_processing=False):
        """
        Run the query using a dummy calculation to see that all required
        input and results are available
        """
        qrunner = _QueryRunner(self, use_multi_processing)
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

    def _cmpids_for_query(self, qpath: HubitQueryPath):
        """
        Find IDs of components that can respond to the "query".
        """
        # TODO: Next two lines should only be executed once in init (speed)
        itempairs = [
            (cmp.id, binding.path)
            for cmp in self.model_cfg.components
            for binding in cmp.provides_results
        ]
        cmp_ids, providerstrings = zip(*itempairs)
        return [cmp_ids[idx] for idx in idxs_for_matches(qpath, providerstrings)]

    def component_for_id(self, compid: str):
        return self.model_cfg.component_for_id[compid]

    def _cmpname_for_query(self, path: HubitQueryPath):
        """Find ID of component that can respond to the "query".
        TODO: bad name... it's the IDs that are returned (ie plural and IDs not name)

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

        # Get the provider function for the query
        return cmp_ids[0]

    def mpath_for_qpath(self, qpath: HubitQueryPath) -> str:
        # Find component that provides queried result
        cmp_ids = self._cmpids_for_query(qpath)
        # Find component
        paths = []
        for cmp_id in cmp_ids:
            cmp = self.model_cfg.component_for_id[cmp_id]
            # Find index in list of binding paths that match query path
            idxs = idxs_for_matches(
                qpath, [binding.path for binding in cmp.provides_results]
            )
            paths.append(cmp.provides_results[idxs[0]].path)
        return paths

    def _expand_query(
        self, qpath: HubitQueryPath, store: bool = True
    ) -> _QueryExpansion:
        """
        Expand query so that any index wildcards are converted to
        real indies

        qpath: The query path to be expanded. Both braced and dotted paths are accepted.
        store: If True some intermediate results will be saved on the
            instance for later use.

        TODO: NEgative indices... prune_tree requires real indices but normalize
        path require all IDX_WILDCARDs be expanded to get the context

        # TODO: Save pruned trees so the worker need not prune top level trees again
        # TODO: save component so we dont have to find top level components again
        """
        # Get all model paths that match the query
        mpaths = self.mpath_for_qpath(qpath)

        # Prepare query expansion object
        qexp = _QueryExpansion(qpath, mpaths)

        # Get the tree that corresponds to the (one) index context
        tree = self.tree_for_idxcontext[qexp.idx_context]

        # Validate that tree and expantion are consistent
        qexp.validate_tree(tree)

        # First store unpruned tree
        if store:
            self._tree_for_qpath[qpath] = tree

        for decomposed_qpath, _mpath in zip(qexp.decomposed_paths, mpaths):
            pruned_tree = tree.prune_from_path(
                decomposed_qpath,
                inplace=False,
            )

            if store:
                # Store pruned tree
                self._tree_for_qpath[decomposed_qpath] = pruned_tree
                self._modelpath_for_querypath[decomposed_qpath] = _mpath

            # Expand the path
            expanded_paths = pruned_tree.expand_path(decomposed_qpath, flat=True)

            qexp.update_expanded_paths(decomposed_qpath, expanded_paths)

        return qexp

    def _compress_response(self, response, queries_expanded: List[_QueryExpansion]):
        """
        Compress the response to reflect queries with index wildcards.
        So if the query has the structure list1[:].list2[:] and is
        rectangular with N1 (2) elements in list1 and N2 (3) elements
        in list2 the compressed response will be a nested list like
        [[00, 01, 02], [10, 11, 12]]
        """
        _response = {}
        for qexp in queries_expanded:
            if not qexp.is_expanded():
                # Path not expanded so no need to compress
                _response[qexp.path] = response[qexp.path]
            else:
                # Get the index IDs from the original query
                idxids = qexp.path.get_index_specifiers()
                tree = self._tree_for_qpath[qexp.path]
                # TODO: relative-spatial-refs. Can we prune earlier on?
                # inplace = False to leave the model state unchanged.
                # This is important for successive get requests
                values_decomp = tree.prune_from_path(
                    qexp.path, inplace=False
                ).none_like()
                # Extract iloc indices for each query in the expanded query
                for expanded_paths in qexp.expanded_paths_for_decomposed_path.values():
                    for path in expanded_paths:
                        slices = path.get_slices()
                        # Only keep ilocs that come from an expansion... otherwise
                        # the dimensions of "values" do no match
                        ilocs = [
                            _slice
                            for _slice, idxid in zip(slices, idxids)
                            if idxid == IDX_WILDCARD
                        ]
                        values_decomp = set_element(
                            values_decomp, response[path], [int(iloc) for iloc in ilocs]
                        )
                _response[qexp.path] = values_decomp

        return _response
