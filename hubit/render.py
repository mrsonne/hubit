from __future__ import annotations
import datetime
import logging
import subprocess
from .config import Query
from typing import TYPE_CHECKING, List, Iterable, cast

from .config import HubitQueryPath, PathIndexRange
from .qrun import _QueryRunner
from .worker import _Worker
from .errors import HubitModelNoInputError

if TYPE_CHECKING:
    from .model import HubitModel

IDX_WILDCARD = PathIndexRange.wildcard_chr


def get_dot(model: HubitModel, query: Query, file_idstr: str):
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
            model.name,
            datetime.datetime.now().strftime("%b %d %Y %H:%M"),
            subprocess.check_output(["whoami"])
            .decode("ascii", errors="ignore")
            .replace("\\", "/"),
        ),
        fontsize=fontsize_small,
        fontname=fontname,
    )

    if len(query.paths) > 0:
        # Render a query

        if not model._input_is_set:
            raise HubitModelNoInputError()

        isquery = True
        filename = "query"

        direction = -1

        # Run validation since this returns (dummy) workers
        workers = model._validate_query(query, use_multi_processing=False)

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
        for component in model.model_cfg.components:
            path = component.provides_results[0].path
            dummy_indices: List[str] = []
            scope_idxid, scope_start = component.scope_start

            # Create dummy indices. Leave indices if specified in model
            for idxspc in path.get_index_specifiers():
                if idxspc.range.is_digit:
                    dummy_indices.append(idxspc.range)
                elif idxspc == scope_idxid:
                    dummy_indices.append(str(scope_start))
                else:
                    dummy_indices.append("0")

            dummy_query = HubitQueryPath(path.set_indices(dummy_indices))

            # Get function and version to init the worker
            (func, version, _) = _QueryRunner._get_func(
                model.base_path, component, components_known={}
            )
            workers.append(
                _Worker(
                    lambda x: x,  # dummy function
                    lambda x: x,  # dummy function
                    component,
                    dummy_query,
                    func,
                    version,
                    tree_for_idxcontext={},  # bypass expansion since we are not hierarchically spawning workers here
                )
            )

    if model.name is not None:
        filename = "{}_{}".format(filename, model.name.lower().replace(" ", "_"))

    if not file_idstr == "":
        filename = "{}_{}".format(filename, file_idstr)

    # Component (calculation) nodes from workers
    with dot.subgraph(name="cluster_calcs", node_attr={"shape": "box"}) as subgraph:
        subgraph.attr(
            rank="same",
            label="Components",
            fontcolor=calc_dark_color,
            style="filled",
            fillcolor=calc_light_color,
            color=calc_light_color,
        )

        for w in workers:
            component = w.component
            scope_range = component.scope_range
            if None in scope_range:
                _scope = "None"
            else:
                # index identifier value is "member of" range
                # TODO: Cast to string to make mypy happy. Should tell it that PathIndexRange is a str subclass
                _scope = " ϵ ".join([str(item) for item in scope_range])

            subgraph.node(
                name=w.id,  # Name identifier of the node
                label=(
                    f"Component index {component._index}"
                    f"\n{component.name}"
                    f"\nIndex scope: {_scope}"
                    f"\nv {w.version}"
                ),
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

    (input_object_ids, results_object_ids) = model._get_binding_ids(
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
        with dot.subgraph(name=prefix_input, node_attr={"shape": "box"}) as subgraph:
            subgraph.attr(
                label="Input data",
                color=input_light_color,
                fillcolor=input_light_color,
                fontcolor=input_dark_color,
                style="filled",
            )
            _render_objects(
                w.id,
                w.binding_map("consumes_input"),
                prefix_input,
                prefix_input,
                input_object_ids[0],
                subgraph,
                arrowsize,
                fontsize_small,
                fontname,
                input_color,
                direction=-direction,
            )

        with dot.subgraph(name=prefix_results, node_attr={"shape": "box"}) as subgraph:

            subgraph.attr(
                label="Results data",
                labelloc="b",  # place at the bottom
                color=results_light_color,
                fillcolor=results_light_color,
                fontcolor=results_dark_color,
                style="filled",
            )

            _render_objects(
                w.id,
                w.binding_map("provides_results"),
                prefix_results,
                prefix_results,
                results_object_ids[0],
                subgraph,
                arrowsize,
                fontsize_small,
                fontname,
                results_color,
                direction=direction,
            )

            # Not all components consume results
            try:
                _render_objects(
                    w.id,
                    w.binding_map("consumes_results"),
                    prefix_results,
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
        if IDX_WILDCARD in pcmp_old or any(idxid in pcmp_old for idxid in idxids):
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
        pathcmps_old = path.components()

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
                _id, is_list = _add_object_for_index(
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
                _id_next, is_list_next = _add_object_for_index(
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
    _edge_with_label(label_for_edgeid, color, constraint, direction, arrowsize, dot)

    # Render nodes that were skipped since they are not connected to other data nodes
    if len(skipped) > 0:
        if direction == 1:
            clusterid_tail = clusterid
            clusterid_head = None
        else:
            clusterid_tail = None
            clusterid_head = clusterid

        label_for_edgeid = {(cluster_node_id, fun_name): skipped}
        _edge_with_label(
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
        tmp = "".join([fstr.format(attrname, " " * spaces) for attrname in attrnames])

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
