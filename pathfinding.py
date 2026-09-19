"""
Classical graph loading and K-shortest-candidate-path generation.
Mirrors the logic from the original Colab notebook.
"""

from itertools import islice

import networkx as nx
import osmnx as ox


def load_graph(graphml_path):
    """Load the exported graph and convert it to a DiGraph, same as the notebook."""
    G = ox.load_graphml(graphml_path)
    G_digraph = ox.convert.to_digraph(G, weight="length")
    return G_digraph


def k_shortest_paths(G, source, target, K=6, weight="length"):
    gen = nx.shortest_simple_paths(G, source, target, weight=weight)
    return list(islice(gen, K))


def path_cost(G, path):
    total = 0.0
    for u, v in zip(path[:-1], path[1:]):
        total += G[u][v]["length"]
    return total


def get_candidates(G, start_node, end_node, K=6):
    paths = k_shortest_paths(G, start_node, end_node, K=K)
    candidates = [(p, path_cost(G, p)) for p in paths]
    candidates.sort(key=lambda x: x[1])
    return candidates
