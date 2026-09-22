from unittest import mock

import networkx as nx
from django.test import SimpleTestCase, override_settings

from fuel.services import local_astar


def _small_graph():
    graph = nx.MultiDiGraph()
    # A tiny 3-node line graph: A -- B -- C, ~1 mile legs.
    graph.add_node("A", y=41.8781, x=-87.6298)
    graph.add_node("B", y=41.8850, x=-87.6298)
    graph.add_node("C", y=41.8920, x=-87.6298)
    graph.add_edge("A", "B", key=0, length=1609.344)
    graph.add_edge("B", "A", key=0, length=1609.344)
    graph.add_edge("B", "C", key=0, length=1609.344)
    graph.add_edge("C", "B", key=0, length=1609.344)
    return graph


class GetRouteLocalAStarTest(SimpleTestCase):
    @override_settings(LOCAL_ASTAR_MAX_MILES=50.0)
    def test_raises_when_straight_line_distance_exceeds_max(self):
        with self.assertRaises(local_astar.LocalAStarUnavailable):
            local_astar.get_route_local_astar((41.8781, -87.6298), (38.6270, -90.1994))

    @override_settings(LOCAL_ASTAR_MAX_MILES=50.0)
    @mock.patch("fuel.services.local_astar.ox.graph_from_bbox")
    def test_returns_geometry_and_distance_for_short_route(self, mock_graph_from_bbox):
        mock_graph_from_bbox.return_value = _small_graph()

        result = local_astar.get_route_local_astar(
            (41.8781, -87.6298), (41.8920, -87.6298)
        )

        self.assertEqual(result.geometry[0], (41.8781, -87.6298))
        self.assertEqual(result.geometry[-1], (41.8920, -87.6298))
        self.assertAlmostEqual(result.distance_miles, 2.0, delta=0.01)
        mock_graph_from_bbox.assert_called_once()

    @override_settings(LOCAL_ASTAR_MAX_MILES=50.0)
    @mock.patch("fuel.services.local_astar.ox.graph_from_bbox")
    def test_raises_when_no_path_found(self, mock_graph_from_bbox):
        graph = nx.MultiDiGraph()
        graph.add_node("A", y=41.8781, x=-87.6298)
        graph.add_node("B", y=41.8920, x=-87.6298)
        mock_graph_from_bbox.return_value = graph

        with self.assertRaises(local_astar.LocalAStarUnavailable):
            local_astar.get_route_local_astar((41.8781, -87.6298), (41.8920, -87.6298))
