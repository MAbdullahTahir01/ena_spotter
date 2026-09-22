import json

from django.conf import settings
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from fuel.api_response import error_response, success_response
from fuel.services.city_search import is_known_city, search_cities
from fuel.services.geo import haversine_miles
from fuel.services.geocode import GeocodeError, geocode_address
from fuel.services.local_astar import LocalAStarUnavailable, get_route_local_astar
from fuel.services.planner import NoFeasibleRouteError, plan_fuel_stops
from fuel.services.routing import RoutingError, cumulative_distances, get_route
from fuel.services.stations import find_candidate_stops


def index_view(request):
    return render(request, "index.html")


@require_http_methods(["GET"])
def health_view(request):
    return success_response("OK")


@require_http_methods(["GET"])
def city_search_view(request):
    query = request.GET.get("q", "")
    return success_response("Cities found", data={"results": search_cities(query)})


@csrf_exempt
@require_http_methods(["POST"])
def route_view(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return error_response("Invalid JSON body")

    if not isinstance(payload, dict):
        return error_response("Both 'start' and 'finish' are required")

    start_query = payload.get("start")
    finish_query = payload.get("finish")
    if (
        not start_query
        or not finish_query
        or not isinstance(start_query, str)
        or not isinstance(finish_query, str)
    ):
        return error_response("Both 'start' and 'finish' are required")

    if start_query.strip().lower() == finish_query.strip().lower():
        return error_response("Start and finish must be different locations")

    if not is_known_city(start_query):
        return error_response(f"'{start_query}' isn't a recognized US city. Pick one from the suggestions.")
    if not is_known_city(finish_query):
        return error_response(f"'{finish_query}' isn't a recognized US city. Pick one from the suggestions.")

    engine = payload.get("engine", "auto")
    if engine not in ("auto", "osrm", "classic_a_star"):
        return error_response("engine must be 'auto', 'osrm', or 'classic_a_star'")

    try:
        start_coords = geocode_address(start_query)
        finish_coords = geocode_address(finish_query)
    except GeocodeError as exc:
        return error_response(str(exc))

    # "auto": use the local A* engine for a short hop, OSRM otherwise.
    # No user choice involved -- the app just picks whichever is a better
    # fit for the distance and reports which one it used.
    if engine == "auto":
        straight_line_miles = haversine_miles(*start_coords, *finish_coords)
        engine = (
            "classic_a_star"
            if straight_line_miles <= settings.LOCAL_ASTAR_MAX_MILES
            else "osrm"
        )

    try:
        if engine == "classic_a_star":
            route = get_route_local_astar(start_coords, finish_coords)
        else:
            route = get_route(start_coords, finish_coords)
    except LocalAStarUnavailable as exc:
        if payload.get("engine", "auto") != "auto":
            return error_response(str(exc))
        # Auto mode never surfaces this to the user -- just fall back.
        engine = "osrm"
        try:
            route = get_route(start_coords, finish_coords)
        except RoutingError as exc:
            return error_response(str(exc), status_code=502)
    except RoutingError as exc:
        return error_response(str(exc), status_code=502)

    cumulative_table = cumulative_distances(route.geometry)
    candidates = find_candidate_stops(cumulative_table)

    try:
        plan = plan_fuel_stops(candidates, total_distance_miles=route.distance_miles)
    except NoFeasibleRouteError as exc:
        return error_response(str(exc))

    fuel_stops = [
        {
            "name": stop.candidate.name,
            "address": stop.candidate.address,
            "city": stop.candidate.city,
            "state": stop.candidate.state,
            "latitude": stop.candidate.latitude,
            "longitude": stop.candidate.longitude,
            "price": stop.candidate.price,
            "gallons_bought": round(stop.gallons_bought, 2),
            "cost": round(stop.cost, 2),
        }
        for stop in plan.stops
    ]

    return success_response(
        "Route found",
        data={
            "engine": engine,
            "distance_miles": round(plan.actual_distance_miles, 1),
            "total_gallons": round(plan.total_gallons, 2),
            "total_cost": round(plan.total_cost, 2),
            "route_geometry": [[lon, lat] for lat, lon in route.geometry],
            "fuel_stops": fuel_stops,
        },
    )
