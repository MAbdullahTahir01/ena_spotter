"""Optional self-hosted routing engine using classic A* (see README for
why it's capped to short routes: fetching a real road graph from the
free Overpass API gets too slow past a small area)."""

from typing import NamedTuple

import networkx as nx
import osmnx as ox
from django.conf import settings

from fuel.services.geo import haversine_miles

METERS_PER_MILE = 1609.344


class LocalAStarUnavailable(Exception):
    pass


class RouteResult(NamedTuple):
    geometry: list[tuple[float, float]]
    distance_miles: float


def _nearest_node(graph: "nx.MultiDiGraph", lat: float, lon: float) -> int:
    return min(
        graph.nodes,
        key=lambda node: haversine_miles(
            lat, lon, graph.nodes[node]["y"], graph.nodes[node]["x"]
        ),
    )


def get_route_local_astar(
    start: tuple[float, float], finish: tuple[float, float]
) -> RouteResult:
    start_lat, start_lon = start
    finish_lat, finish_lon = finish

    straight_line_miles = haversine_miles(start_lat, start_lon, finish_lat, finish_lon)
    max_miles = settings.LOCAL_ASTAR_MAX_MILES
    if straight_line_miles > max_miles:
        raise LocalAStarUnavailable(
            f"classic_a_star only supports routes under {max_miles:g} miles "
            f"(requested ~{straight_line_miles:.0f} miles) -- fetching a real "
            "road graph from the free Overpass API doesn't scale past a small "
            "regional area within a single request. Use the default OSRM "
            "engine for longer routes."
        )

    graph = ox.graph_from_bbox(
        bbox=(
            min(start_lon, finish_lon) - 0.15,
            min(start_lat, finish_lat) - 0.15,
            max(start_lon, finish_lon) + 0.15,
            max(start_lat, finish_lat) + 0.15,
        ),
        network_type="drive",
        simplify=True,
    )

    orig = _nearest_node(graph, start_lat, start_lon)
    dest = _nearest_node(graph, finish_lat, finish_lon)

    def heuristic(u: int, v: int) -> float:
        return (
            haversine_miles(
                graph.nodes[u]["y"], graph.nodes[u]["x"],
                graph.nodes[v]["y"], graph.nodes[v]["x"],
            )
            * METERS_PER_MILE
        )

    try:
        path = nx.astar_path(graph, orig, dest, heuristic=heuristic, weight="length")
    except nx.NetworkXNoPath as exc:
        raise LocalAStarUnavailable("No local road-graph path found between start and finish") from exc

    geometry = [(graph.nodes[node]["y"], graph.nodes[node]["x"]) for node in path]
    distance_meters = sum(
        graph[path[i]][path[i + 1]][0]["length"] for i in range(len(path) - 1)
    )

    return RouteResult(geometry=geometry, distance_miles=distance_meters / METERS_PER_MILE)
