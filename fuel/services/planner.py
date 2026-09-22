from typing import NamedTuple

from django.conf import settings

from fuel.services.stations import StationCandidate


class NoFeasibleRouteError(Exception):
    pass


class FuelStop(NamedTuple):
    candidate: StationCandidate
    gallons_bought: float
    cost: float


class FuelPlan(NamedTuple):
    stops: list[FuelStop]
    total_gallons: float
    total_cost: float
    actual_distance_miles: float


def _start_leg_price(candidates: list[StationCandidate], max_range_miles: float) -> float:
    """Price for the vehicle's first tank of fuel: cheapest station within
    the first tank's range, else cheapest station anywhere on the route,
    else a fallback default (see FUEL_DEFAULT_PRICE_PER_GALLON)."""
    in_range = [c.price for c in candidates if c.distance_along_route_miles <= max_range_miles]
    if in_range:
        return min(in_range)
    if candidates:
        return min(c.price for c in candidates)
    return settings.FUEL_DEFAULT_PRICE_PER_GALLON


INF = float("inf")


def _node_distances(candidates: list[StationCandidate]) -> list[float]:
    """Distance-along-route for each node, where node 0 is the virtual
    start and nodes 1..n are the candidates (already sorted by distance)."""
    return [0.0] + [c.distance_along_route_miles for c in candidates]


def _price_at_node(node: int, candidates: list[StationCandidate], start_leg_price: float) -> float:
    """Price paid for fuel bought at `node` (node 0 is the start, not a real station)."""
    return start_leg_price if node == 0 else candidates[node - 1].price


def _detour_miles(node: int, candidates: list[StationCandidate]) -> float:
    """Extra round-trip driving to leave the route, actually reach the
    station at `node`, and come back (node 0 is the start, right on the
    route by definition, so it has no detour)."""
    return 0.0 if node == 0 else 2 * candidates[node - 1].distance_off_route_miles


def _cheapest_arrival_costs(
    candidates: list[StationCandidate],
    distances: list[float],
    max_range_miles: float,
    mpg: float,
    start_leg_price: float,
) -> tuple[list[float], list[int]]:
    """Classic "gas station on a line" DP: for each node, find the
    cheapest way to arrive there with a full tank, coming from any
    earlier node reachable within one tank of range.

    Returns (cost_to_reach, best_previous_node) arrays indexed by node,
    where cost_to_reach[0] == 0 (the start) and best_previous_node[i] is
    -1 for any node that couldn't be reached.
    """
    n = len(candidates)
    cost_to_reach = [INF] * (n + 1)
    cost_to_reach[0] = 0.0
    best_previous_node = [-1] * (n + 1)

    for node in range(1, n + 1):
        for earlier_node in range(0, node):
            if cost_to_reach[earlier_node] == INF:
                continue
            leg_miles = distances[node] - distances[earlier_node] + _detour_miles(node, candidates)
            if leg_miles < 0 or leg_miles > max_range_miles:
                continue
            price = _price_at_node(earlier_node, candidates, start_leg_price)
            cost = cost_to_reach[earlier_node] + (leg_miles / mpg) * price
            if cost < cost_to_reach[node]:
                cost_to_reach[node] = cost
                best_previous_node[node] = earlier_node

    return cost_to_reach, best_previous_node


def _cheapest_finish(
    candidates: list[StationCandidate],
    distances: list[float],
    cost_to_reach: list[float],
    total_distance_miles: float,
    max_range_miles: float,
    mpg: float,
) -> tuple[float, int | None]:
    """Of every node that can be reached at all, find the one whose
    final leg to the destination is cheapest overall."""
    best_total_cost = INF
    best_last_node = None

    for node in range(1, len(candidates) + 1):
        if cost_to_reach[node] == INF:
            continue
        final_leg_miles = total_distance_miles - distances[node]
        if final_leg_miles < 0 or final_leg_miles > max_range_miles:
            continue
        total_cost = cost_to_reach[node] + (final_leg_miles / mpg) * candidates[node - 1].price
        if total_cost < best_total_cost:
            best_total_cost = total_cost
            best_last_node = node

    return best_total_cost, best_last_node


def _backtrack_stop_nodes(best_previous_node: list[int], best_last_node: int) -> list[int]:
    """Walk the DP's parent pointers back from the last stop to the
    start, returning the stop nodes in travel order (start excluded)."""
    stop_nodes = []
    node = best_last_node
    while node != 0:
        stop_nodes.append(node)
        node = best_previous_node[node]
    stop_nodes.reverse()
    return stop_nodes


def _build_fuel_stops(
    stop_nodes: list[int],
    candidates: list[StationCandidate],
    distances: list[float],
    total_distance_miles: float,
    mpg: float,
) -> list[FuelStop]:
    """Turn the chosen stop nodes into FuelStops, each carrying the
    gallons bought there to cover the leg up to the *next* stop."""
    stops: list[FuelStop] = []
    for position, node in enumerate(stop_nodes):
        candidate = candidates[node - 1]
        is_last_stop = position + 1 == len(stop_nodes)
        if is_last_stop:
            next_distance = total_distance_miles
            next_detour = 0.0
        else:
            next_node = stop_nodes[position + 1]
            next_distance = distances[next_node]
            next_detour = _detour_miles(next_node, candidates)
        leg_miles = next_distance - candidate.distance_along_route_miles + next_detour
        gallons_bought = leg_miles / mpg
        cost = gallons_bought * candidate.price
        stops.append(FuelStop(candidate=candidate, gallons_bought=gallons_bought, cost=cost))
    return stops


def plan_fuel_stops(
    candidates: list[StationCandidate],
    total_distance_miles: float,
    max_range_miles: float | None = None,
    mpg: float | None = None,
) -> FuelPlan:
    if max_range_miles is None:
        max_range_miles = settings.FUEL_MAX_RANGE_MILES
    if mpg is None:
        mpg = settings.FUEL_MPG

    total_gallons = total_distance_miles / mpg
    start_leg_price = _start_leg_price(candidates, max_range_miles)

    # Trip fits in one tank: no stop needed, but fuel still has to be
    # bought for the whole distance.
    if total_distance_miles <= max_range_miles:
        return FuelPlan(
            stops=[],
            total_gallons=total_gallons,
            total_cost=total_gallons * start_leg_price,
            actual_distance_miles=total_distance_miles,
        )

    distances = _node_distances(candidates)
    cost_to_reach, best_previous_node = _cheapest_arrival_costs(
        candidates, distances, max_range_miles, mpg, start_leg_price
    )
    best_total_cost, best_last_node = _cheapest_finish(
        candidates, distances, cost_to_reach, total_distance_miles, max_range_miles, mpg
    )

    if best_last_node is None:
        raise NoFeasibleRouteError(
            "No feasible fuel plan: a route leg exceeds the max range with no reachable station."
        )

    stop_nodes = _backtrack_stop_nodes(best_previous_node, best_last_node)
    stops = _build_fuel_stops(stop_nodes, candidates, distances, total_distance_miles, mpg)

    # Actual miles driven include a round trip off the route for every chosen
    # stop, not just total_distance_miles -- keep total_gallons and the
    # reported trip distance consistent with that (and with best_total_cost,
    # which already prices those miles).
    detour_miles_driven = sum(2 * stop.candidate.distance_off_route_miles for stop in stops)
    actual_distance_miles = total_distance_miles + detour_miles_driven
    total_gallons = actual_distance_miles / mpg

    # best_total_cost (not sum(stop.cost)) is the true total: it also
    # includes the initial leg's cost, which isn't tied to any listed stop.
    return FuelPlan(
        stops=stops,
        total_gallons=total_gallons,
        total_cost=best_total_cost,
        actual_distance_miles=actual_distance_miles,
    )
