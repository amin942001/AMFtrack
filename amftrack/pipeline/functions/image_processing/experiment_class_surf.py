import os
import pandas as pd
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from amftrack.pipeline.functions.image_processing.extract_graph import (
    generate_skeleton,
    from_nx_to_tab,
    prune_graph,
)
import pickle
from matplotlib.widgets import CheckButtons
import scipy.io as sio
import imageio
from pymatreader import read_mat
from matplotlib import colors
from collections import Counter
from datetime import datetime, timedelta
import cv2
from typing import List, Tuple
import ast
from scipy import sparse

from amftrack.util.sys import get_dirname
from amftrack.pipeline.functions.image_processing.node_id import reconnect_degree_2
from amftrack.plotutil import plot_t_tp1
from amftrack.pipeline.functions.image_processing.node_id import orient
from amftrack.util.aliases import node_coord_dict, binary_image, coord, coord_int


class Experiment:
    """Represents a single plate experiment over time."""

    def __init__(self, plate: int, directory: str):
        self.plate = plate
        self.directory = directory

        self.folders: List[str]
        self.dates: List[datetime]
        self.positions: List[node_coord_dict]  # TODO(FK): in which referential?
        self.nx_graph: List[nx.Graph]
        self.skeletons: List[sparse.dok_matrix]
        self.compressed: List[binary_image]
        # Coordinates of stiched images at each t given in the referential of the timestep t
        self.image_coordinates: List[List[coord_int]]
        self.hyphaes = None

    def __repr__(self):
        return f"Experiment({self.directory}, {self.plate})"

    def load(self, folders: pd.DataFrame, labeled=True):
        """Loads the graphs from the different time points and other useful attributes"""
        self.folders = folders
        self.image_coordinates = [None] * len(folders)
        dates_datetime = [
            datetime.strptime(row["date"], "%d.%m.%Y, %H:%M:")
            for index, row in folders.iterrows()
        ]
        self.dates = dates_datetime
        self.dates.sort()
        nx_graph_poss = []
        for date in self.dates:
            print(date)

            directory_name = get_dirname(date, self.plate)
            path_snap = self.directory + directory_name
            if labeled:
                suffix = "/Analysis/nx_graph_pruned_labeled.p"
            else:
                suffix = "/Analysis/nx_graph_pruned.p"
            path_save = path_snap + suffix
            (g, pos) = pickle.load(open(path_save, "rb"))
            nx_graph_poss.append((g, pos))

        nx_graphs = [nx_graph_pos[0] for nx_graph_pos in nx_graph_poss]
        poss = [nx_graph_pos[1] for nx_graph_pos in nx_graph_poss]
        # nx_graph_clean=[]
        # for graph in nx_graphs:
        #     S = [graph.subgraph(c).copy() for c in nx.connected_components(graph)]
        #     len_connected=[len(nx_graph.nodes) for nx_graph in S]
        #     nx_graph_clean.append(S[np.argmax(len_connected)])
        self.positions = poss
        self.nx_graph = nx_graphs
        labels = {node for g in self.nx_graph for node in g}
        self.nodes = []
        for label in labels:
            self.nodes.append(Node(label, self))
        xpos = [pos[0] for poss in self.positions for pos in poss.values()]
        ypos = [pos[1] for poss in self.positions for pos in poss.values()]
        self.ts = len(self.dates)
        self.labeled = labeled

    def load_compressed_skel(self, factor=5):
        """
        Computes and store a sparse binary image of the whole squeleton for each timestep.
        Computes and store a compressed binary image of the whole squeleton for each timestep.
        """
        # TODO(FK): rename function, `load` is ambiguous
        skeletons = []
        for nx_graph in self.nx_graph:
            skeletons.append(generate_skeleton(nx_graph, dim=(30000, 60000)))
        self.skeletons = skeletons
        compressed_images = []
        for t in range(len(self.dates)):
            compressed_images.append(self.compress_skeleton(t, factor))
        self.compressed = compressed_images

    def compress_skeleton(self, t: int, factor: int) -> binary_image:
        """
        Computes an image, reduced in size by 'factor', from a the sparse squeleton matrix
        of timestep t.
        """
        # TODO(FK): move to util? (there is a duplicate in util)
        shape = self.skeletons[t].shape
        final_picture = np.zeros(shape=(shape[0] // factor, shape[1] // factor))
        for pixel in self.skeletons[t].keys():
            x = min(round(pixel[0] / factor), shape[0] // factor - 1)
            y = min(round(pixel[1] / factor), shape[1] // factor - 1)
            final_picture[x, y] += 1
        return final_picture >= 1

    def copy(self, experiment):
        self.folders = experiment.folders
        self.positions = experiment.positions
        self.nx_graph = experiment.nx_graph
        self.dates = experiment.dates
        self.plate = experiment.plate
        self.hyphaes = None

        self.ts = experiment.ts
        labels = {node for g in self.nx_graph for node in g}
        self.nodes = []
        for label in labels:
            self.nodes.append(Node(label, self))

    def save(self, path=f"Data/"):
        tabs_labeled = []
        for i, date in enumerate(self.dates):
            tabs_labeled.append(from_nx_to_tab(self.nx_graph[i], self.positions[i]))
        for i, date in enumerate(self.dates):
            #             tabs_labeled[i].to_csv(path + f"graph_{date}_{self.plate}_full_labeled.csv")
            sio.savemat(
                path + f"graph_{date}_{self.plate}_full_labeled.mat",
                {name: col.values for name, col in tabs_labeled[i].items()},
            )

    def pickle_save(self, path):
        pickle.dump(self, open(path + f"experiment.pick", "wb"))

    def pickle_load(self, path):
        self = pickle.load(open(path + f"experiment.pick", "rb"))

    def get_node(self, label: str):
        return Node(label, self)

    def get_edge(self, begin, end):
        return Edge(begin, end, self)

    def get_growing_tips(self, t, threshold=80):
        # TODO(FK): growth patterns not defined
        growths = {
            tip: sum([len(branch) for branch in self.growth_patterns[t][tip]])
            for tip in self.growth_patterns[t].keys()
        }
        growing_tips = [node for node in growths.keys() if growths[node] >= threshold]
        return growing_tips

    def pinpoint_anastomosis(self, t):
        # TODO(FK): self.connections?
        nx_graph_tm1 = self.nx_graph[t]
        nx_grapht = self.nx_graph[t + 1]
        from_tip = self.connections[t]
        pos_tm1 = self.positions[t]
        anastomosis = []
        origins = []
        tips = [node for node in nx_graph_tm1.nodes if nx_graph_tm1.degree(node) == 1]
        number_anastomosis = 0

        def dist_branch(node, nx_graph, pos):
            mini = np.inf
            for edge in nx_graph.edges:
                pixel_list = nx_graph.get_edge_data(*edge)["pixel_list"]
                if (
                    np.linalg.norm(np.array(pixel_list[0]) - np.array(pos[node]))
                    <= 5000
                ):
                    distance = np.min(
                        np.linalg.norm(
                            np.array(pixel_list) - np.array(pos[node]), axis=1
                        )
                    )
                    if distance < mini:
                        mini = distance
            return mini

        def count_neighbors_is_from_root(equ_list, nx_graph, root):
            count = 0
            for neighbor in nx_graph.neighbors(root):
                if neighbor in equ_list:
                    count += 1
            return count

        for tip in tips:
            #         print(tip)
            consequence = from_tip[tip]
            for node in consequence:
                if (
                    node in nx_grapht.nodes
                    and nx_grapht.degree(node) >= 3
                    and count_neighbors_is_from_root(consequence, nx_grapht, node) < 2
                ):
                    #                 if node==2753:
                    #                     print(count_neighbors_is_from_root(consequence,nx_grapht,node))
                    #                     print(list(nx_grapht.neighbors(node)))
                    anastomosis.append(node)
                    origins.append(tip)
                    number_anastomosis += 1
            if (
                tip not in nx_grapht.nodes
                and dist_branch(tip, nx_grapht, pos_tm1) <= 30
                and nx_graph_tm1.get_edge_data(*list(nx_graph_tm1.edges(tip))[0])[
                    "weight"
                ]
                >= 20
            ):
                origins.append(tip)
                number_anastomosis += 1 / 2
        return (anastomosis, origins, number_anastomosis)

    def get_image_coordinates(self, t: int) -> List[coord_int]:
        """
        For a time step t, return the coordinates of all the images in the general referential.
        """
        if self.image_coordinates is None:
            raise Exception("Must load directories first")
        if self.image_coordinates[t] is None:
            date = self.dates[t]
            directory_name = get_dirname(date, self.plate)
            path_tile = os.path.join(
                self.directory, directory_name, "Img/TileConfiguration.txt.registered"
            )
            tileconfig = pd.read_table(
                path_tile,
                sep=";",
                skiprows=4,
                header=None,
                converters={2: ast.literal_eval},
                skipinitialspace=True,
            )
            raw_coordinates = list(tileconfig[2])
            n_im = len(raw_coordinates)
            cmin = np.min([raw_coordinates[i][0] for i in range(n_im)])
            rmin = np.min([raw_coordinates[i][1] for i in range(n_im)])
            coordinates = [
                [raw_coordinates[i][0] - cmin, raw_coordinates[i][1] - rmin]
                for i in range(n_im)
            ]
            self.image_coordinates[t] = coordinates
        return self.image_coordinates[t]

    def find_image_pos(
        self, xs: int, ys: int, t: int, local=False
    ) -> Tuple[List, List[coord]]:
        """
        For coordinates (xs, yx) in the full size stiched image,
        returns a list of original images (before stiching) that contain the coordinate.
        And for each found image, returns the coordinates of the point of interest in
        the image.
        """
        date = self.dates[t]
        directory_name = get_dirname(date, self.plate)
        path_snap = self.directory + directory_name
        path_tile = path_snap + "/Img/TileConfiguration.txt.registered"
        skel = read_mat(path_snap + "/Analysis/skeleton_pruned_realigned.mat")
        Rot = skel["R"]
        trans = skel["t"]
        rottrans = np.dot(np.linalg.inv(Rot), np.array([xs, ys] - trans))
        ys, xs = round(rottrans[0]), round(rottrans[1])
        tileconfig = pd.read_table(
            path_tile,
            sep=";",
            skiprows=4,
            header=None,
            converters={2: ast.literal_eval},
            skipinitialspace=True,
        )
        xs_yss = list(tileconfig[2])
        xes = [xs_ys[0] for xs_ys in xs_yss]
        yes = [xs_ys[1] for xs_ys in xs_yss]
        cmin = np.min(xes)
        cmax = np.max(xes)
        rmin = np.min(yes)
        rmax = np.max(yes)
        ximg = xs
        yimg = ys

        def find(xsub: List, ysub: List, x: float, y: float):
            """
            :param x: x coordinate of point of interest
            :param xsub: List of x coordinate of all the images
            :return: list of indexes of images which contain (x,y)
            """
            indexes = []
            for i in range(len(xsub)):
                if (
                    x >= xsub[i] - cmin
                    and x < xsub[i] - cmin + 4096
                    and y >= ysub[i] - rmin
                    and y < ysub[i] - rmin + 3000
                ):
                    indexes.append(i)
            return indexes

        indsImg = find(xes, yes, ximg, yimg)
        possImg = [
            ximg - np.array(xes)[indsImg] + cmin + 1,
            yimg - np.array(yes)[indsImg] + rmin + 1,
        ]
        paths = []
        for index in indsImg:
            name = tileconfig[0][index]
            imname = "/Img/" + name.split("/")[-1]
            directory_name = get_dirname(date, self.plate)
            path = self.directory + directory_name + imname
            paths.append(path)
        ims = [imageio.imread(path) for path in paths]
        return (ims, possImg)

    def plot_raw(self, t, figsize=(10, 9)):
        """Plot the full stiched image compressed (otherwise too heavy)"""
        date = self.dates[t]
        directory_name = get_dirname(date, self.plate)
        path_snap = self.directory + directory_name
        im = read_mat(path_snap + "/Analysis/raw_image.mat")["raw"]
        fig = plt.figure(figsize=figsize)
        ax = fig.add_subplot(111)
        ax.imshow(im)

    def plot(self, ts, node_lists=[], shift=(0, 0), compress=5, save="", time=None):
        """
        Plots several nodes at several timesteps, with different colors, on one another.
        Useful for the debuging of node attribution.
        """
        global check
        right = 0.90
        top = 0.90
        if len(save) >= 1:
            fig = plt.figure(figsize=(14, 12))
            size = 10
        else:
            fig = plt.figure()
            size = 5
        ax = fig.add_subplot(111)
        scale = 1 / len(ts)
        power = len(ts)
        if compress != 5:
            compressed_images = []
            for i, t in enumerate(ts):
                compressed_images.append(self.compress_skeleton(t, compress))
        else:
            compressed_images = []
            for i, t in enumerate(ts):
                compressed_images.append(self.compressed[t])
        visibility = [True for t in ts]
        final_image = scale * compressed_images[0] * visibility[0]
        for i, compressed_image in enumerate(compressed_images[1:]):
            final_image = np.power(
                final_image**power
                + ((i + 2) * scale * compressed_image * visibility[i + 1]) ** power,
                1 / power,
            )
        l1 = ax.imshow(final_image, cmap="plasma", interpolation="none", vmin=0, vmax=1)
        rax = plt.axes([0.05, 0.4, 0.1, 0.15])
        labels = [f"{4*t}h" for t in ts]
        check = CheckButtons(rax, labels, visibility)

        def func(label):
            index = labels.index(label)
            visibility[index] = not visibility[index]
            final_image = visibility[0] * scale * compressed_images[0]
            for i, compressed_image in enumerate(compressed_images[1:]):
                final_image = np.power(
                    final_image**power
                    + visibility[i + 1] * ((i + 2) * scale * compressed_image) ** power,
                    1 / power,
                )
            l1.set_data(final_image)
            plt.draw()

        check.on_clicked(func)
        if len(node_lists) > 0:
            for i, node_list in enumerate(node_lists):
                grey = (i + 1) / len(labels)
                bbox = dict(boxstyle="circle", fc=colors.rgb2hex((grey, grey, grey)))
                #             ax.text(right, top, time,
                #                 horizontalalignment='right',
                #                 verticalalignment='bottom',
                #                 transform=ax.transAxes,color='white')
                for node in node_list:
                    #                     print(self.positions[ts[i]])
                    if node in self.positions[ts[i]].keys():
                        t = ax.text(
                            (self.positions[ts[i]][node][1] - shift[1]) // compress,
                            (self.positions[ts[i]][node][0] - shift[0]) // compress,
                            str(node),
                            ha="center",
                            va="center",
                            size=size,
                            bbox=bbox,
                        )
        if len(save) >= 1:
            plt.savefig(save)
            plt.close(fig)
        else:
            plt.show()


def save_graphs(exp):
    nx_graph_poss = []
    for i, date in enumerate(exp.dates):
        directory_name = get_dirname(date, exp.plate)
        path_snap = exp.directory + directory_name
        labeled = exp.labeled
        print(date, labeled)

        if labeled:
            suffix = "/Analysis/nx_graph_pruned_labeled2.p"
            path_save = path_snap + suffix
            # print(path_save)
            g = exp.nx_graph[i]
            pos = exp.positions[i]
            pickle.dump((g, pos), open(path_save, "wb"))


def load_graphs(exp, indexes=None):
    nx_graph_poss = []
    labeled = exp.labeled
    if indexes == None:
        indexes = range(exp.ts)
    for index, date in enumerate(exp.dates):
        directory_name = get_dirname(date, exp.plate)
        path_snap = exp.directory + directory_name
        if labeled:
            suffix = "/Analysis/nx_graph_pruned_labeled2.p"
        else:
            suffix = "/Analysis/nx_graph_pruned.p"
        path_save = path_snap + suffix
        (g, pos) = pickle.load(open(path_save, "rb"))
        if index in indexes:
            nx_graph_poss.append((g, pos))
        else:
            edge_empty = {edge: None for edge in g.edges}
            nx.set_edge_attributes(g, edge_empty, "pixel_list")
            nx_graph_poss.append((g, pos))
    nx_graphs = [nx_graph_pos[0] for nx_graph_pos in nx_graph_poss]
    poss = [nx_graph_pos[1] for nx_graph_pos in nx_graph_poss]
    #         nx_graph_clean=[]
    #         for graph in nx_graphs:
    #             S = [graph.subgraph(c).copy() for c in nx.connected_components(graph)]
    #             len_connected=[len(nx_graph.nodes) for nx_graph in S]
    #             nx_graph_clean.append(S[np.argmax(len_connected)])
    exp.positions = poss
    exp.nx_graph = nx_graphs


def load_skel(exp, ts):
    skeletons = []
    for t, nx_graph in enumerate(exp.nx_graph):
        if t in ts:
            skeletons.append(generate_skeleton(nx_graph, dim=(30000, 60000)))
        else:
            skeletons.append(None)
    exp.skeletons = skeletons


def plot_raw_plus(
    exp: Experiment,
    t0: int,
    node_list: List[int],
    shift=(0, 0),
    n=0,
    compress=5,
    center=None,
    radius_imp=None,
    fig=None,
    ax=None,
):
    """
    Plots a group of node on the compressed full stiched image of the skeleton.
    """
    date = exp.dates[t0]
    directory_name = get_dirname(date, exp.plate)
    path_snap = exp.directory + directory_name
    skel = read_mat(path_snap + "/Analysis/skeleton_pruned_realigned.mat")
    Rot = skel["R"]
    trans = skel["t"]
    im = read_mat(path_snap + "/Analysis/raw_image.mat")["raw"]
    size = 5
    if fig is None:
        fig = plt.figure()
        ax = fig.add_subplot(111)
        alpha = 0.3
        cmap = "jet"
    else:
        alpha = 0.3
        cmap = "gray"
    grey = 1 - 1 / (n + 2)
    if center is None:
        center = np.mean(
            [
                exp.positions[t0][node]
                for node in node_list
                if node in exp.positions[t0].keys()
            ],
            axis=0,
        )
        radius = np.max(
            [
                np.linalg.norm(exp.positions[t0][node] - center)
                for node in node_list
                if node in exp.positions[t0].keys()
            ]
        )
        radius = np.max((radius, radius_imp))
    else:
        radius = radius_imp
    boundaries = (
        np.max(
            np.transpose(((0, 0), (center - 2 * radius).astype(int) // compress)),
            axis=1,
        ),
        (center + 2 * radius).astype(int) // compress,
    )
    # boundaries = np.flip(boundaries,axis = 1)
    height, width = im.shape[:2]
    trans_mat = np.concatenate(
        (np.linalg.inv(Rot), np.flip(trans.reshape(-1, 1) // compress)), axis=1
    )
    im = cv2.warpAffine(src=im, M=trans_mat, dsize=(width, height))
    # print(radius)
    im = im[boundaries[0][0] : boundaries[1][0], boundaries[0][1] : boundaries[1][1]]
    _ = ax.imshow(im, alpha=alpha, cmap=cmap)
    bbox = dict(boxstyle="circle", fc=colors.rgb2hex((grey, grey, grey)))
    #             ax.text(right, top, time,
    #                 horizontalalignment='right',
    #                 verticalalignment='bottom',
    #                 transform=ax.transAxes,color='white')
    shift = (max(0, boundaries[0][0] * compress), max(0, boundaries[0][1] * compress))
    for node in node_list:
        #                     print(self.positions[ts[i]])
        if node in exp.positions[t0].keys():
            xs, ys = exp.positions[t0][node]
            # rottrans = np.dot(np.linalg.inv(Rot), np.array([xs, ys] - trans))
            # rottrans = np.dot(Rot, np.array([xs, ys]))+trans//5
            # ys, xs = round(rottrans[0]), round(rottrans[1])
            xs, ys = ys, xs
            t = ax.text(
                (xs - shift[1]) // compress,
                (ys - shift[0]) // compress,
                str(node),
                ha="center",
                va="center",
                size=size,
                bbox=bbox,
            )
    return (fig, ax, center, radius)


class Node:
    """Represents a single node, through time in an experiment."""

    def __init__(self, label, experiment):
        self.experiment: Experiment = experiment
        self.label: str = label

    def __eq__(self, other):
        return self.label == other.label

    def __repr__(self):
        return f"Node({self.label})"

    def __str__(self):
        return str(self.label)

    def __hash__(self):
        return self.label

    def get_pseudo_identity(self, t):
        # NB(FK): This method is a duplicate of the function find_node_equ
        if self.is_in(t):
            return self
        else:
            mini = np.inf
            poss = self.experiment.positions[t]
            pos_root = np.mean([self.pos(t) for t in self.ts()], axis=0)
            for node in self.experiment.nx_graph[t]:
                distance = np.linalg.norm(poss[node] - pos_root)
                if distance < mini:
                    mini = distance
                    identifier = node
        return Node(identifier, self.experiment)

    def neighbours(self, t: int) -> List["Node"]:
        """Returns a list of neighboors of the node at a specific timestep."""
        return [
            self.experiment.get_node(node)
            for node in self.experiment.nx_graph[t].neighbors(self.label)
        ]

    def is_in(self, t: int) -> bool:
        """Determines if the node is present at timestep t in the graph."""
        return self.label in self.experiment.nx_graph[t].nodes

    def degree(self, t):
        return self.experiment.nx_graph[t].degree(self.label)

    def edges(self, t):
        return [
            self.experiment.get_edge(self, neighbour)
            for neighbour in self.neighbours(t)
        ]

    def pos(self, t):
        return self.experiment.positions[t][self.label]

    def ts(self) -> List[int]:
        """Returns a list of all the timestep at which the node is present."""
        return [t for t in range(len(self.experiment.nx_graph)) if self.is_in(t)]

    def show_source_image(self, t: int, tp1: int):
        """
        Two use cases:
        If t==tp1:
        This function plots the original image from time t containing the node.
        As there can be several original images (because of overlap), the
        darker image is choosen (why?)
        If t!=tp1:
        This function plots the original images from time t and tp1 on one another
        """
        pos = self.pos(t)
        x, y = pos[0], pos[1]
        ims, posimg = self.experiment.find_image_pos(x, y, t)
        # Choosing which image to show
        i = np.argmax([np.mean(im) for im in ims])
        if t != tp1:
            posp1 = self.pos(tp1)
            xp1, yp1 = posp1[0], posp1[1]
            imsp1, posimgp1 = self.experiment.find_image_pos(xp1, yp1, tp1)
            ip1 = np.argmax([np.mean(im) for im in imsp1])
            plot_t_tp1(
                [self.label],
                [self.label],
                {self.label: (posimg[1][i], posimg[0][i])},
                {self.label: (posimgp1[1][ip1], posimgp1[0][ip1])},
                ims[i],
                imsp1[ip1],
            )
        else:
            plot_t_tp1(
                [self.label],
                [],
                {self.label: (posimg[1][i], posimg[0][i])},
                None,
                ims[i],
                ims[i],
                gray=True,
            )


def get_distance(node1, node2, t) -> float:
    """
    Computes the distance between two nodes in micro-meter at timestep t.
    """
    pixel_conversion_factor = 1.725
    nodes = nx.shortest_path(
        node1.experiment.nx_graph[t],
        source=node1.label,
        target=node2.label,
        weight="weight",
    )
    edges = [
        Edge(
            node1.experiment.get_node(nodes[i]),
            node1.experiment.get_node(nodes[i + 1]),
            node1.experiment,
        )
        for i in range(len(nodes) - 1)
    ]
    length = 0
    for edge in edges:
        length_edge = 0
        pixels = edge.pixel_list(t)
        for i in range(len(pixels) // 10 + 1):
            if i * 10 <= len(pixels) - 1:
                length_edge += np.linalg.norm(
                    np.array(pixels[i * 10])
                    - np.array(pixels[min((i + 1) * 10, len(pixels) - 1)])
                )
        length += length_edge
    return length * pixel_conversion_factor


def find_node_equ(node, t) -> Node:
    """
    At a given timestep t, determines the node which is the closest to the average position
    of 'node' over time.
    If 'node' exists at timestep t, then it will return 'node'.
    If 'node' has never existed before timestep t, raises an error.
    This function is used when there is a possible missidentification of a node over time.
    """
    # TODO(FK): This function is computationnaly very expensive.
    assert node.ts()[0] <= t
    if node.is_in(t):
        return node
    else:
        mini = np.inf
        poss = node.experiment.positions[t]
        pos_root = np.mean([node.pos(t) for t in node.ts()], axis=0)  # me
        for node_candidate in node.experiment.nx_graph[t]:
            distance = np.linalg.norm(poss[node_candidate] - pos_root)
            if distance < mini:
                mini = distance
                identifier = node_candidate
        return Node(identifier, node.experiment)


class Edge:
    """Edge object through time in an experiment."""

    def __init__(self, begin: Node, end: Node, experiment: Experiment):
        self.begin = begin
        self.end = end
        self.experiment = experiment

    def __eq__(self, other):
        return (self.begin == other.begin and self.end == other.end) or (
            self.end == other.begin and self.begin == other.end
        )

    def __repr__(self):
        return f"Edge({self.begin},{self.end})"

    def __str__(self):
        return str((self.begin, self.end))

    def __hash__(self):
        return frozenset({self.begin, self.end}).__hash__()

    def is_in(self, t):
        return (self.begin.label, self.end.label) in self.experiment.nx_graph[t].edges

    def ts(self):
        return [t for t in range(self.experiment.ts) if self.is_in(t)]

    def pixel_list(self, t):
        return orient(
            self.experiment.nx_graph[t].get_edge_data(self.begin.label, self.end.label)[
                "pixel_list"
            ],
            self.begin.pos(t),
        )

    def width(self, t):
        return self.experiment.nx_graph[t].get_edge_data(
            self.begin.label, self.end.label
        )["width"]

    def orientation_whole(self, t):
        pixel_list = np.array(self.pixel_list(t))
        vector = pixel_list[-1] - pixel_list[0]
        unit_vector = vector / np.linalg.norm(vector)
        vertical_vector = np.array([-1, 0])
        dot_product = np.dot(vertical_vector, unit_vector)
        if (
            vertical_vector[1] * vector[0] - vertical_vector[0] * vector[1] >= 0
        ):  # determinant
            angle = np.arccos(dot_product) / (2 * np.pi) * 360
        else:
            angle = -np.arccos(dot_product) / (2 * np.pi) * 360
        return angle

    def orientation_begin(self, t, length=20):
        pixel_list = np.array(self.pixel_list(t))
        vector = pixel_list[min(length, len(pixel_list) - 1)] - pixel_list[0]
        unit_vector = vector / np.linalg.norm(vector)
        vertical_vector = np.array([-1, 0])
        dot_product = np.dot(vertical_vector, unit_vector)
        if (
            vertical_vector[1] * vector[0] - vertical_vector[0] * vector[1] >= 0
        ):  # determinant
            angle = np.arccos(dot_product) / (2 * np.pi) * 360
        else:
            angle = -np.arccos(dot_product) / (2 * np.pi) * 360
        return angle

    def orientation_end(self, t, length=20):
        pixel_list = np.array(self.pixel_list(t))
        vector = pixel_list[-1] - pixel_list[max(0, len(pixel_list) - 1 - length)]
        unit_vector = vector / np.linalg.norm(vector)
        vertical_vector = np.array([-1, 0])
        dot_product = np.dot(vertical_vector, unit_vector)
        if (
            vertical_vector[1] * vector[0] - vertical_vector[0] * vector[1] >= 0
        ):  # determinant
            angle = np.arccos(dot_product) / (2 * np.pi) * 360
        else:
            angle = -np.arccos(dot_product) / (2 * np.pi) * 360
        return angle


class Hyphae:
    def __init__(self, tip):
        self.experiment = tip.experiment
        self.ts = tip.ts()
        self.end = tip
        self.root = None
        self.mother = None

    def __eq__(self, other):
        return self.end.label == other.end.label

    def __repr__(self):
        return f"Hyphae({self.end},{self.root})"

    def __str__(self):
        return str((self.end, self.root))

    def __hash__(self):
        return self.end.label

    def get_root(self, t):
        assert not self.root is None
        if self.root.is_in(t):
            return self.root
        else:
            mini = np.inf
            poss = self.experiment.positions[t]
            pos_root = np.mean([self.root.pos(t) for t in self.root.ts()], axis=0)
            for node in self.experiment.nx_graph[t]:
                if self.experiment.nx_graph[t].degree(node) >= 3:
                    distance = np.linalg.norm(poss[node] - pos_root)
                    if distance < mini:
                        mini = distance
                        identifier = node
        return Node(identifier, self.experiment)

    def get_edges(self, t, length=100):
        first_neighbour = self.end.neighbours(t)[0]
        last_node = self.end
        current_node = first_neighbour
        current_edge = Edge(last_node, current_node, self.experiment)
        moving_on_hyphae = True
        edges = [current_edge]
        nodes = [last_node, current_node]
        i = 0
        while moving_on_hyphae:
            i += 1
            if i >= 100:
                print(t, self.end, current_node)
            if i >= 110:
                break
            #                 print ('moving',current_node)
            if current_node.degree(t) < 2:
                #                     print(current_node.degree(t),current_node)
                moving_on_hyphae = False
            else:
                maxi = -np.inf
                orientation = current_edge.orientation_end(t, length)
                for neighbours_t in current_node.neighbours(t):
                    #                     print (neighbours_t)
                    candidate_edge = Edge(current_node, neighbours_t, self.experiment)
                    orientation_candidate = candidate_edge.orientation_begin(t, length)
                    angle = np.cos(
                        (orientation - orientation_candidate) / 360 * 2 * np.pi
                    )
                    if angle > maxi:
                        maxi = angle
                        next_node_candidate = neighbours_t
                #                     print(maxi,next_node_candidate)
                candidate_edge = Edge(
                    current_node, next_node_candidate, self.experiment
                )
                orientation_candidate = candidate_edge.orientation_begin(t, length)
                maxi_compet = -np.inf
                #                     print('compet')
                for neighbours_t in current_node.neighbours(t):
                    if neighbours_t != last_node:
                        competitor_edge = Edge(
                            neighbours_t, current_node, self.experiment
                        )
                        orientation_competitor = competitor_edge.orientation_end(
                            t, length
                        )
                        angle = np.cos(
                            (orientation_competitor - orientation_candidate)
                            / 360
                            * 2
                            * np.pi
                        )
                        if angle > maxi_compet:
                            maxi_compet = angle
                            competitor = neighbours_t
                #                             print(neighbours_t,angle)
                #                     print(maxi_compet,competitor)
                if maxi_compet > maxi:
                    moving_on_hyphae = False
                else:
                    last_node, current_node = current_node, next_node_candidate
                    current_edge = Edge(last_node, current_node, self.experiment)
                    edges.append(current_edge)
                    nodes.append(current_node)
        #         while moving:
        #             c= move_hyphae(llast_node,ccurrent_node)
        #             edges += c[0]
        #             nodes += c[1]
        #             competitor = c[2]
        # #             print('moving back', nodes[-1],competitor)
        #             move_backward = move_hyphae(nodes[-1],competitor)
        #             end_node_move_backward = move_backward[1][-1]
        #             if end_node_move_backward in nodes:
        # #                 print('restarting',competitor,nodes[-1])
        #                 llast_node,ccurrent_node = c[2],nodes[-1]
        #             else:
        #                 moving=False
        root = nodes[-1]
        edges = edges
        nodes = nodes
        return (root, edges, nodes)

    def get_nodes_within(self, t):
        nodes = nx.shortest_path(
            self.experiment.nx_graph[t],
            source=self.get_root(t).label,
            target=self.end.label,
            weight="weight",
        )
        edges = [
            Edge(
                self.experiment.get_node(nodes[i]),
                self.experiment.get_node(nodes[i + 1]),
                self.experiment,
            )
            for i in range(len(nodes) - 1)
        ]
        return (nodes, edges)

    def get_length_pixel(self, t):
        nodes, edges = self.get_nodes_within(t)
        length = 0
        for edge in edges:
            length += len(edge.pixel_list(t))
        return length

    def get_length_um(self, t):
        pixel_conversion_factor = 1.725
        nodes, edges = self.get_nodes_within(t)
        length = 0
        for edge in edges:
            length_edge = 0
            pixels = edge.pixel_list(t)
            for i in range(len(pixels) // 10 + 1):
                if i * 10 <= len(pixels) - 1:
                    length_edge += np.linalg.norm(
                        np.array(pixels[i * 10])
                        - np.array(pixels[min((i + 1) * 10, len(pixels) - 1)])
                    )
            #         length_edge+=np.linalg.norm(np.array(pixels[len(pixels)//10-1*10-1])-np.array(pixels[-1]))
            length += length_edge
        return length * pixel_conversion_factor

    def get_mother(self):
        candidate_mother = []
        for hyphae in self.experiment.hyphaes:
            for t in hyphae.ts:
                if self.root in hyphae.get_nodes_within(t):
                    candidate_mother.append(hyphae)
        self.mother = candidate_mother

    def update_ts(self):
        # self.ts = sorted(set(self.end.ts()).intersection(set(self.root.ts())))
        # It may make more sense to consider that root may not exist at a certain time point in which case one can simply use the closest node
        self.ts = self.end.ts()

    def get_orientation(self, t, start, length=50):
        nodes, edges = self.get_nodes_within(t)
        pixel_list_list = []
        #     print(edges[start:])
        for edge in edges[start:]:
            pixel_list_list += edge.pixel_list(t)
        pixel_list = np.array(pixel_list_list)
        vector = pixel_list[min(length, len(pixel_list) - 1)] - pixel_list[0]
        unit_vector = vector / np.linalg.norm(vector)
        vertical_vector = np.array([-1, 0])
        dot_product = np.dot(vertical_vector, unit_vector)
        if (
            vertical_vector[1] * vector[0] - vertical_vector[0] * vector[1] >= 0
        ):  # determinant
            angle = np.arccos(dot_product) / (2 * np.pi) * 360
        else:
            angle = -np.arccos(dot_product) / (2 * np.pi) * 360
        return angle


# def plot_raw_plus(exp,t0,node_list,shift=(0,0),compress=5):
#     date = exp.dates[t0]
#     directory_name = get_dirname(date,exp.plate)
#     path_snap = exp.directory + directory_name
#     skel = read_mat(path_snap + "/Analysis/skeleton_pruned_realigned.mat")
#     Rot = skel["R"]
#     trans = skel["t"]
#     im = read_mat(path_snap+'/Analysis/raw_image.mat')['raw']
#     fig = plt.figure()
#     size = 5
#     ax = fig.add_subplot(111)
#     grey = 1
#     ax.imshow(im)
#     bbox = dict(boxstyle="circle", fc=colors.rgb2hex((grey, grey, grey)))
#     #             ax.text(right, top, time,
#     #                 horizontalalignment='right',
#     #                 verticalalignment='bottom',
#     #                 transform=ax.transAxes,color='white')
#     for node in node_list:
#         #                     print(self.positions[ts[i]])
#         if node in exp.positions[t0].keys():
#             xs,ys = exp.positions[t0][node]
#             rottrans = np.dot(np.linalg.inv(Rot), np.array([xs, ys] - trans))
#             ys, xs = round(rottrans[0]), round(rottrans[1])
#             t = ax.text(
#                 (xs - shift[1]) // compress,
#                 (ys - shift[0]) // compress,
#                 str(node),
#                 ha="center",
#                 va="center",
#                 size=size,
#                 bbox=bbox,
#             )
#     plt.show()


if __name__ == "__main__":
    # exp = Experiment(4, "directory")
    # print(exp)
    from amftrack.util.sys import (
        update_plate_info_local,
        get_current_folders_local,
        test_path,
    )

    directory = test_path + "/"  # TODO(FK): fix this error
    plate_name = "20220330_2357_Plate19"
    update_plate_info_local(directory)
    folder_df = get_current_folders_local(directory)
    selected_df = folder_df.loc[folder_df["folder"] == plate_name]
    i = 0
    plate = int(list(selected_df["folder"])[i].split("_")[-1][5:])
    folder_list = list(selected_df["folder"])
    directory_name = folder_list[i]
    exp = Experiment(plate, directory)
    exp.load(selected_df.loc[selected_df["folder"] == directory_name], labeled=False)

    r = exp.find_image_pos(10000, 5000, t=0)
    print(r)

    print(exp.get_image_coordinates(0))
