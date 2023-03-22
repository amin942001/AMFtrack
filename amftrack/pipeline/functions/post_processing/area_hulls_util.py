import pickle

import networkx as nx
import numpy as np
import pandas as pd
import scipy
from scipy import spatial
from shapely.geometry import Polygon, Point

from amftrack.notebooks.analysis.util import splitPolygon, get_time
from amftrack.pipeline.functions.post_processing.util import is_in_study_zone
from amftrack.util.sys import temp_path
import os

def get_length_shape(exp,shape,t):
    skeleton = exp.skeletons[t]
    intersect = exp.multipoints[t].loc[exp.multipoints[t].within(shape)]
    tot_length = len(intersect)*1.725
    return(tot_length)


def get_hulls(exp, ts):
    hulls = []
    for t in ts:
        nx_graph = exp.nx_graph[t]
        threshold = 0.1
        S = [nx_graph.subgraph(c).copy() for c in nx.connected_components(nx_graph)]
        selected = [
            g
            for g in S
            if g.size(weight="weight") * len(g.nodes) / 10**6 >= threshold
        ]
        polys = Polygon()
        if len(selected) >= 0:
            area_max = 0
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
                    area_hull = poly.area * 1.725**2 / (1000**2)
                    polys = polys.union(poly)
        print(t, len(selected), polys.area)
        hulls.append(polys)
    return hulls


def ring_area(hull1, hull2):
    return np.sum(hull2.difference(hull1).area) * 1.725**2 / (1000**2)


def get_nodes_in_ring(hull1, hull2, t, exp):
    nodes = [
        node
        for node in exp.nodes
        if node.is_in(t)
        and hull2.contains(Point(node.pos(t)))
        and not hull1.contains(Point(node.pos(t)))
        and np.all(is_in_study_zone(node, t, 1000, 200))
    ]
    return nodes


def get_hyphae_in_ring(hull1, hull2, t, exp):
    hyphae = [
        hyph
        for hyph in exp.hyphaes
        if hyph.end.is_in(t)
        and hull2.contains(Point(hyph.end.pos(t)))
        and not hull1.contains(Point(hyph.end.pos(t)))
        and np.all(is_in_study_zone(hyph.end, t, 1000, 200))
    ]
    return hyphae


def get_length_in_ring(hull1, hull2, t, exp):
    nodes = get_nodes_in_ring(hull1, hull2, t, exp)
    edges = {edge for node in nodes for edge in node.edges(t)}
    tot_length = np.sum(
        [np.linalg.norm(edge.end.pos(t) - edge.begin.pos(t)) * 1.725/2 for edge in edges]
    )
    return tot_length


def get_length_in_ring_new(hull1, hull2, t, exp):
    shape = hull2.difference(hull1)
    tot_length = get_length_shape(exp,shape,t)
    print(tot_length)
    return tot_length


def get_density_in_ring_bootstrap(hull1, hull2, t, exp, n_resamples = 100):
    shape = hull2.difference(hull1)
    geoms = splitPolygon(shape, 100, 100).geoms
    densities = [get_length_shape(exp,geom,t)/(geom.area* 1.725**2 / (1000**2)) for geom in geoms]
    res = scipy.stats.bootstrap((np.array(densities),), np.mean,
                                vectorized=True,
                                method="basic",
                                n_resamples=n_resamples)

    return res


def get_biovolume_in_ring(hull1, hull2, t, exp):
    nodes = get_nodes_in_ring(hull1, hull2, t, exp)
    edges = {edge for node in nodes for edge in node.edges(t)}
    tot_biovolume = np.sum(
        [
            np.pi
            * (edge.width(t) / 2) ** 2
            * np.linalg.norm(edge.end.pos(t) - edge.begin.pos(t))
            * 1.725
            for edge in edges
        ]
    )
    return tot_biovolume


def get_growing_tips(hull1, hull2, t, exp, rh_only):
    nodes = get_nodes_in_ring(hull1, hull2, t, exp)
    tips = [
        node
        for node in nodes
        if node.degree(t) == 1 and node.is_in(t + 1) and len(node.ts()) > 2
    ]
    growing_tips = [
        node
        for node in tips
        if np.linalg.norm(node.pos(t) - node.pos(node.ts()[-1])) >= 40
    ]
    if rh_only:
        growing_rhs = [
            node
            for node in growing_tips
            if np.linalg.norm(node.pos(node.ts()[0]) - node.pos(node.ts()[-1])) >= 1500
        ]
        return growing_rhs
    else:
        return growing_tips


def get_rate_anas_in_ring(hull1, hull2, t, exp, rh_only):
    growing_tips = get_growing_tips(hull1, hull2, t, exp, rh_only)
    anas_tips = [
        tip
        for tip in growing_tips
        if tip.degree(t) == 1
        and tip.degree(t + 1) == 3
        and 1 not in [tip.degree(t) for t in [tau for tau in tip.ts() if tau > t]]
    ]
    timedelta = get_time(exp, t, t + 1)
    return len(anas_tips) / timedelta


def get_rate_branch_in_ring(hull1, hull2, t, exp, rh_only):
    growing_tips = get_growing_tips(hull1, hull2, t, exp, rh_only)
    new_tips = [tip for tip in growing_tips if tip.ts()[0] == t]
    timedelta = get_time(exp, t, t + 1)
    return len(new_tips) / timedelta


def get_rate_stop_in_ring(hull1, hull2, t, exp, rh_only):
    growing_tips = get_growing_tips(hull1, hull2, t, exp, rh_only)
    stop_tips = [
        tip
        for tip in growing_tips
        if np.linalg.norm(tip.pos(t + 1) - tip.pos(tip.ts()[-1])) <= 40
        and tip.ts()[-1] != t + 1
        and tip.degree(t + 1) == 1
    ]
    timedelta = get_time(exp, t, t + 1)
    return len(stop_tips) / timedelta


def get_num_active_tips_in_ring(hull1, hull2, t, exp, rh_only):
    growing_tips = get_growing_tips(hull1, hull2, t, exp, rh_only)
    return len(growing_tips)


def get_regular_hulls(num, exp, ts):
    hulls = get_hulls(exp, ts)
    areas = [hull.area * 1.725**2 / (1000**2) for hull in hulls]
    area_incr = areas[-1] - areas[0]
    length_incr = np.sqrt(area_incr)
    incr = length_incr / num
    regular_hulls = [hulls[0]]
    init_area = areas[0]
    indexes = [0]
    current_length = incr
    for i in range(num - 1):
        current_area = init_area + current_length**2
        index = min([i for i in range(len(areas)) if areas[i] >= current_area])
        indexes.append(index)
        current_length += incr
        regular_hulls.append(hulls[index])
    return (regular_hulls, indexes)


def get_regular_hulls_area_fixed(exp, ts, incr):
    """Gets the hulls of an experiment with a fixed area increase incr"""
    path = os.path.join(
        temp_path,
        f"hulls_{exp.unique_id}_{incr}_"
        f"{np.sum(pd.util.hash_pandas_object(exp.folders.iloc[ts]))}.pick",
    )
    if os.path.isfile(path):
        (regular_hulls, indexes) = pickle.load(open(path, "rb"))
    else:
        hulls = get_hulls(exp, ts)
        areas = [np.sum(hull.area) * 1.725**2 / (1000**2) for hull in hulls]
        area_incr = np.max(areas) - areas[0]
        num = int(area_incr / incr)
        regular_hulls = [hulls[0]]
        init_area = areas[0]
        indexes = [0]
        current_area = init_area
        for i in range(num - 1):
            current_area += incr
            index = min([i for i in range(len(areas)) if areas[i] >= current_area])
            indexes.append(index)
            regular_hulls.append(hulls[index])

        pickle.dump((regular_hulls, indexes), open(path, "wb"))
    return (regular_hulls, indexes)