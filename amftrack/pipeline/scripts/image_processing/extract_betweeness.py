import sys

from amftrack.pipeline.functions.image_processing.extract_width_fun import (
    get_width_info,
    get_width_info_new,
)


from amftrack.pipeline.functions.image_processing.experiment_class_surf import (
    Experiment,
)
from amftrack.util.sys import temp_path
import pickle
import networkx as nx
import pandas as pd
from amftrack.pipeline.functions.post_processing.extract_study_zone import (
    load_study_zone,
)
from amftrack.pipeline.functions.image_processing.experiment_util import (
    get_all_edges,
    get_all_nodes
)
from amftrack.pipeline.functions.post_processing.time_hypha import is_in_study_zone
from amftrack.pipeline.functions.image_processing.experiment_class_surf import (
    load_graphs,
)
import numpy as np

directory = str(sys.argv[1])
skip = eval(sys.argv[2])
resolution = eval(sys.argv[3])
i = int(sys.argv[-1])
op_id = int(sys.argv[-2])

run_info = pd.read_json(f"{temp_path}/{op_id}.json", dtype={"unique_id": str})
# plate = list(run_info['PrincePos'])[i]
# Sometime plate in param file is inconsistent with folder name...
# plate = int(list(run_info['folder'])[i].split('_')[-1][5:])
folder_list = list(run_info["folder"])
folder_list.sort()
directory_name = folder_list[i]
plate = int(directory_name.split("_")[-1][5:])

exp = Experiment(directory)
folders = run_info.loc[run_info["folder"] == directory_name]
exp.load(folders)
for t in range(len(folders)):
    exp.load_tile_information(t)
t = 0
load_graphs(exp, directory)
exp.save_location = ''

load_study_zone(exp)

edges = get_all_edges(exp, t)
nodes = get_all_nodes(exp, t)
weights = {(edge.begin.label,edge.end.label) : edge.length_um(t) for edge in edges}
nx.set_edge_attributes(exp.nx_graph[t] , weights, "length")
nodes_source = [node for node in nodes if not is_in_study_zone(node,t,1000,150)[1] and is_in_study_zone(node,t,1000,150)[0]]
nodes_sink = [node for node in nodes if is_in_study_zone(node,t,1000,150)[1] and node.degree(t)==1]

G = exp.nx_graph[t]
S = [G.subgraph(c).copy() for c in nx.connected_components(G)]
len_connected=[len(nx_graph.nodes) for nx_graph in S]
G_connected = S[np.argmax(len_connected)]
source = [node.label for node in nodes_source if node.label in G_connected]
sink = [node.label for node in nodes_sink if node.label in G_connected]
current_flow_betweeness = nx.edge_current_flow_betweenness_centrality_subset(G_connected,source,sink,weight = "length")
betweeness = nx.edge_betweenness_centrality_subset(G_connected,source,sink,weight = "length",normalized=True)
for edge in exp.nx_graph[t].edges:
    if edge not in current_flow_betweeness.keys() and (edge[1],edge[0]) not in current_flow_betweeness.keys():
        current_flow_betweeness[edge] = 0
        betweeness[edge] = 0
nx.set_edge_attributes(exp.nx_graph[t] , current_flow_betweeness, "current_flow_betweenness")
nx.set_edge_attributes(exp.nx_graph[t] , betweeness, "betweenness")
(G, pos) = exp.nx_graph[0], exp.positions[0]
path_snap = directory + directory_name

pickle.dump((G, pos), open(f"{path_snap}/Analysis/nx_graph_pruned_labeled.p", "wb"))
