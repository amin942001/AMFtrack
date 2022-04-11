from amftrack.pipeline.functions.image_processing.experiment_class_surf import (
    Edge,
    Node,
)
from amftrack.pipeline.functions.post_processing.util import (
    get_length_um_edge,
    is_in_study_zone,
)
import numpy as np
from scipy import spatial
from shapely.geometry import Polygon, shape
import networkx as nx
from amftrack.util.sys import *


def is_out_study(exp, t, args):
    return ("out_study", int(t > exp.reach_out))


def get_length_study_zone(exp, t, args):
    length = 0
    for edge in exp.nx_graph[t].edges:
        edge_obj = Edge(Node(edge[0], exp), Node(edge[1], exp), exp)
        is_in_end = np.all(is_in_study_zone(edge_obj.end, t, 1000, 150))
        is_in_begin = np.all(is_in_study_zone(edge_obj.begin, t, 1000, 150))
        if is_in_end and is_in_begin:
            length += get_length_um_edge(edge_obj, t)
    return ("tot_length_study", length)


def get_length_in_ring_rough(exp, t, args):
    length = 0
    for edge in exp.nx_graph[t].edges:
        edge_obj = Edge(Node(edge[0], exp), Node(edge[1], exp), exp)
        is_in_end = np.all(is_in_study_zone(edge_obj.end, t, 1000, 150))
        is_in_begin = np.all(is_in_study_zone(edge_obj.begin, t, 1000, 150))
        if is_in_end and is_in_begin:
            length += np.linalg.norm(edge.end.pos(t) - edge.begin.pos(t)) * 1.725
    return ("tot_length_study_rough", length)


def get_area(exp, t, args):
    nodes = np.array([node.pos(t) for node in exp.nodes if node.is_in(t)])
    if len(nodes) > 0:
        hull = spatial.ConvexHull(nodes)
        poly = Polygon([nodes[vertice] for vertice in hull.vertices])
        area = poly.area * 1.725**2 / (1000**2)
    else:
        area = 0
    return ("area", area)


def get_area_study_zone(exp, t, args):
    nodes = np.array(
        [
            node.pos(t)
            for node in exp.nodes
            if node.is_in(t) and np.all(is_in_study_zone(node, t, 1000, 150))
        ]
    )
    if len(nodes) > 3:
        hull = spatial.ConvexHull(nodes)
        poly = Polygon([nodes[vertice] for vertice in hull.vertices])
        area = poly.area * 1.725**2 / (1000**2)
    else:
        area = 0
    return ("area_study", area)


def get_area_separate_connected_components(exp, t, args):
    nx_graph = exp.nx_graph[t]
    threshold = 0.1
    S = [nx_graph.subgraph(c).copy() for c in nx.connected_components(nx_graph)]
    selected = [
        g for g in S if g.size(weight="weight") * len(g.nodes) / 10**6 >= threshold
    ]
    area = 0
    for g in selected:
        nodes = np.array(
            [
                node.pos(t)
                for node in exp.nodes
                if node.is_in(t)
                and np.all(is_in_study_zone(node, t, 1000, 150))
                and (node.label in g.nodes)
            ]
        )
        if len(nodes) > 3:
            hull = spatial.ConvexHull(nodes)
            poly = Polygon([nodes[vertice] for vertice in hull.vertices])
            area += poly.area * 1.725**2 / (1000**2)
    return ("area_sep_comp", area)


def get_num_tips(exp, t, args):
    return (
        "num_tips",
        len([node for node in exp.nodes if node.is_in(t) and node.degree(t) == 1]),
    )


def get_num_tips_study_zone(exp, t, args):
    return (
        "num_tips_study",
        len(
            [
                node
                for node in exp.nodes
                if node.is_in(t)
                and node.degree(t) == 1
                and np.all(is_in_study_zone(node, t, 1000, 150))
            ]
        ),
    )


def get_num_nodes(exp, t, args):
    return ("num_nodes", len([node for node in exp.nodes if node.is_in(t)]))


def get_num_nodes_study_zone(exp, t, args):
    return (
        "num_nodes_study",
        len(
            [
                node
                for node in exp.nodes
                if node.is_in(t) and np.all(is_in_study_zone(node, t, 1000, 150))
            ]
        ),
    )


def get_length(exp, t, args):
    length = 0
    for edge in exp.nx_graph[t].edges:
        edge_obj = Edge(Node(edge[0], exp), Node(edge[1], exp), exp)
        length += get_length_um_edge(edge_obj, t)
    return ("tot_length", length)


def get_num_trunks(exp, t, args):
    return ("num_trunks", int(exp.num_trunk))


def get_L_RH(exp, t, args):
    plate = exp.folders["Plate"].unique()[0]
    time_plate_info, global_hypha_info, time_hypha_info = get_data_tables()
    table = global_hypha_info.loc[global_hypha_info["Plate"] == plate].copy()
    table["log_length"] = np.log10((table["tot_length_C"] + 1).astype(float))
    table["is_rh"] = (table["log_length"] >= 3.36).astype(int)
    table = table.set_index("hypha")
    hyphaes = table.loc[
        (table["strop_track"] >= t)
        & (table["timestep_init_growth"] <= t)
        & ((table["out_of_ROI"].isnull()) | (table["out_of_ROI"] > t))
    ].index
    rh = hyphaes.loc[(hyphaes["is_rh"] == 1)].index
    select_time = time_hypha_info.loc[time_hypha_info["Plate"] == plate]
    L_rh = np.sum(
        select_time.loc[(select_time["end"].isin(rh)) & (select_time["timestep"] == t)][
            "tot_length_C"
        ]
    )
    return ("L_rh", L_rh)


def get_L_BAS(exp, t, args):
    plate = exp.folders["Plate"].unique()[0]
    time_plate_info, global_hypha_info, time_hypha_info = get_data_tables(
        redownload=True
    )
    table = global_hypha_info.loc[global_hypha_info["Plate"] == plate].copy()
    table["log_length"] = np.log10((table["tot_length_C"] + 1).astype(float))
    table["is_rh"] = (table["log_length"] >= 3.36).astype(int)
    table = table.set_index("hypha")
    hyphaes = table.loc[
        (table["strop_track"] >= t)
        & (table["timestep_init_growth"] <= t)
        & ((table["out_of_ROI"].isnull()) | (table["out_of_ROI"] > t))
    ]
    bas = hyphaes.loc[(hyphaes["is_rh"] == 0)].index
    select_time = time_hypha_info.loc[time_hypha_info["Plate"] == plate]
    L_bas = np.sum(
        select_time.loc[
            (select_time["end"].isin(bas)) & (select_time["timestep"] == t)
        ]["tot_length_C"]
    )
    return ("L_BAS", L_bas)