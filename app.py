import time

import folium
import streamlit as st
from streamlit_folium import st_folium

from pathfinding import load_graph, get_candidates
from quantum_utils import grover_threshold_search

st.set_page_config(page_title="Quantum Route Finder", layout="wide")

GRAPH_PATH = "map.graphml"

PALETTE = [
    "#9e9e9e", "#8d99ae", "#b5838d", "#ffb4a2",
    "#e07a5f", "#3d5a80", "#588157", "#a8dadc",
]
WINNER_COLOR = "#e63946"


# ------------------------------------------------------------------
# Load graph once and cache it
# ------------------------------------------------------------------
@st.cache_resource
def get_graph():
    return load_graph(GRAPH_PATH)


G = get_graph()

# graph centroid, for centering the map
xs = [data["x"] for _, data in G.nodes(data=True)]
ys = [data["y"] for _, data in G.nodes(data=True)]
CENTER = [sum(ys) / len(ys), sum(xs) / len(xs)]


# ------------------------------------------------------------------
# Session state
# ------------------------------------------------------------------
if "start_point" not in st.session_state:
    st.session_state.start_point = None
if "end_point" not in st.session_state:
    st.session_state.end_point = None
if "result" not in st.session_state:
    st.session_state.result = None


def reset_selection():
    st.session_state.start_point = None
    st.session_state.end_point = None
    st.session_state.result = None


# ------------------------------------------------------------------
# Sidebar controls
# ------------------------------------------------------------------
st.sidebar.title(" Settings")
K = st.sidebar.slider("Number of candidate paths (K)", min_value=2, max_value=10, value=6)
shots = st.sidebar.select_slider("Quantum shots per search", options=[64, 128, 256, 512, 1024], value=512)
st.sidebar.button(" Reset selection", on_click=reset_selection)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**How to use:**\n"
    "1. Click the map once for your **start** point.\n"
    "2. Click again for your **end** point.\n"
    "3. Press **Find Best Route**.\n"
    "4. Click again anytime to start a new selection."
)

st.title("Quantum Route Finder")
st.caption("Classical K-shortest-path search + a real Grover-based quantum search to pick the best one.")

col_map, col_info = st.columns([2, 1])

# ------------------------------------------------------------------
# Build the folium map
# ------------------------------------------------------------------
with col_map:
    m = folium.Map(location=CENTER, zoom_start=15, tiles="OpenStreetMap")

    if st.session_state.start_point:
        folium.Marker(
            location=st.session_state.start_point,
            tooltip="Start",
            icon=folium.Icon(color="green", icon="play"),
        ).add_to(m)

    if st.session_state.end_point:
        folium.Marker(
            location=st.session_state.end_point,
            tooltip="End",
            icon=folium.Icon(color="red", icon="stop"),
        ).add_to(m)

    result = st.session_state.result
    if result:
        for i, (path, cost) in enumerate(result["candidates"]):
            coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in path]
            is_winner = (i == result["best_idx"])
            folium.PolyLine(
                coords,
                color=WINNER_COLOR if is_winner else PALETTE[i % len(PALETTE)],
                weight=6 if is_winner else 3,
                opacity=1.0 if is_winner else 0.55,
                tooltip=f"Path {i} — cost {cost:.0f} m" + ("Quantum pick" if is_winner else ""),
            ).add_to(m)

    map_state = st_folium(m, height=560, width=700, key="route_map")

# handle new clicks
if map_state and map_state.get("last_clicked"):
    clicked = (map_state["last_clicked"]["lat"], map_state["last_clicked"]["lng"])

    if st.session_state.start_point is None:
        st.session_state.start_point = clicked
        st.session_state.result = None
        st.rerun()
    elif st.session_state.end_point is None and clicked != st.session_state.start_point:
        st.session_state.end_point = clicked
        st.session_state.result = None
        st.rerun()
    elif st.session_state.end_point is not None:
        # third click -> start a new selection
        st.session_state.start_point = clicked
        st.session_state.end_point = None
        st.session_state.result = None
        st.rerun()


# ------------------------------------------------------------------
# Info / results panel
# ------------------------------------------------------------------
with col_info:
    st.subheader("Selection")
    st.write(f"**Start:** {st.session_state.start_point or '— click the map —'}")
    st.write(f"**End:** {st.session_state.end_point or '— click the map —'}")

    can_search = st.session_state.start_point and st.session_state.end_point
    if st.button("Find Best Route", disabled=not can_search, use_container_width=True):
        with st.spinner("Finding candidate routes and running the quantum search..."):
            start_node = ox_nearest = None
            import osmnx as ox
            start_node = ox.nearest_nodes(
                G, X=st.session_state.start_point[1], Y=st.session_state.start_point[0]
            )
            end_node = ox.nearest_nodes(
                G, X=st.session_state.end_point[1], Y=st.session_state.end_point[0]
            )

            if start_node == end_node:
                st.error("Start and end points snap to the same road node — pick two points further apart.")
            else:
                candidates = get_candidates(G, start_node, end_node, K=K)
                t0 = time.time()
                best_idx, hist = grover_threshold_search(candidates, shots=shots)
                elapsed = time.time() - t0

                st.session_state.result = {
                    "candidates": candidates,
                    "best_idx": best_idx,
                    "hist": hist,
                    "elapsed": elapsed,
                }
                st.rerun()

    result = st.session_state.result
    if result:
        best_path, best_cost = result["candidates"][result["best_idx"]]
        speed_mps = 40 * 1000 / 3600  # assume 40 km/h average
        eta_min = (best_cost / speed_mps) / 60

        st.markdown("###Quantum-selected route")
        st.metric("Distance", f"{best_cost:.0f} m")
        st.metric("Estimated time (@40 km/h)", f"{eta_min:.1f} min")
        st.caption(f"Quantum search took {result['elapsed']:.2f}s (simulated).")

        st.markdown("### Candidate paths")
        for i, (_, cost) in enumerate(result["candidates"]):
            marker = " ⭐ " if i == result["best_idx"] else ""
            st.write(f"Path {i}{marker} — {cost:.0f} m")

        if result["hist"]:
            st.markdown("### Quantum measurement histogram")
            st.caption("Distribution of measured indices across all Grover search rounds.")
            st.bar_chart(result["hist"])
    elif not can_search:
        st.info("Click two points on the map to get started.")
