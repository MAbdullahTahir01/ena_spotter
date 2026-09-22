# Fuel Route Optimizer

You give it a start and a finish city in the US. It asks OSRM (a free
routing service) for the driving route, then figures out the cheapest
way to fuel up along it, assuming the car can go 500 miles on a tank
and gets 10 miles per gallon. You get back the route, where to stop
for gas, and how much the whole trip will cost in fuel.

It's a Django app with a small frontend on top: a map, a start/finish
form, and a summary of distance, gallons, and cost.

For a walkthrough of what this does, how the routing engine and the
fuel-stop planner each work, and a worked real-world example, see
`Fuel_Route_Planner_Guide.docx`.

## Why it's built this way

**Routing.** The assignment says to find a free routing API rather
than build one yourself, so that's what this does: OSRM's public
server, one call per request. OSRM already solves routing with
Contraction Hierarchies under the hood, which is the same technique
you'd reach for if you were building a road-network router from
scratch, so there's no point reimplementing it.

There's also an experimental second engine you can request
(`"engine": "classic_a_star"`, or the app picks it for you
automatically on short trips): it fetches a small real road graph and
runs classic A* on it directly, instead of calling OSRM. I tried this
mainly to see if it was feasible. It turns out A* itself is nearly
instant once you have the graph, but fetching that graph from the free
Overpass API takes tens of seconds even for an 18-mile area, and would
never finish for a real cross-country trip. So this engine only kicks
in under 50 miles, and otherwise the app quietly falls back to OSRM.
Details are in `fuel/services/local_astar.py`.

**Picking where to stop for gas.** This is the classic "gas station on
a highway" problem: you can't skip a station if the next one is out of
range, and among the ones you can reach you want the cheapest. It's
solved with a small dynamic-programming pass in
`fuel/services/planner.py` rather than a greedy pick, because a greedy
"always take the nearest reachable cheap station" approach can miss a
cheaper station a bit further down the road. The one thing worth
calling out: the car still needs fuel for its first leg, even if that
leg is short enough that no stop is required. That fuel is priced at
whatever the cheapest reachable station would have charged, so the
total cost is never a meaningless $0 for a real trip.

**Finding candidate stations.** The provided price list has ~8,000
rows with only city/state, no coordinates. Those get geocoded once,
offline, against a free GeoNames city list, so there's no need to hit
a geocoding API 8,000 times. At request time, stations within a few
miles of the route are found with a cheap bounding-box check before
doing the more expensive point-to-route distance math.

**City autocomplete.** The start/finish fields suggest cities as you
type. That's backed by the same offline city list, so it doesn't add
another external API call.

## Getting started from nothing

Two ways to run this: plain Python (a venv), or Docker. Both use a
local SQLite database by default — no external database needed to try
this out.

### Option A: plain Python

If you're opening this for the first time with a totally empty
setup (no `.env`, no database, nothing installed), this is the
complete path:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py loaddata fuel_stations
.venv/bin/python manage.py runserver
```

Then open `http://127.0.0.1:8000/` and try a start/finish, e.g.
"Chicago, IL" to "Denver, CO".

### Option B: Docker, no local Python needed

A prebuilt image is already published, so this is the fastest way to
try it with nothing installed but Docker itself:

```bash
docker run -p 8000:8000 mirzarule/ena-spotter:latest
```

Then open `http://127.0.0.1:8000/`. This runs the exact same app
against a SQLite database inside the container (fine for trying it
out; that data won't persist between container restarts). To build
the image yourself instead of pulling it:

```bash
docker build -t ena-spotter .
docker run -p 8000:8000 ena-spotter
```

### Configuration

You don't need to create a `.env` file — every setting has a working
default (see `config/settings.py`). If you want to change something
(the assumed mpg, the vehicle range, timeouts, etc.), copy
`.env.example` to `.env` and edit it; that file lists every setting
the app reads, with the default value next to each one.

**Database:** by default (no `DATABASE_URL` set), the app uses a local
SQLite file — nothing to configure, nothing external required. Set
`DATABASE_URL` (e.g. to a Postgres/Neon connection string) to use that
instead; this is what a real deployment would set, since SQLite alone
doesn't fit most free hosting platforms (see `config/settings.py`).

The `loaddata fuel_stations` step loads a fixture that's already
committed to the repo, so you don't need to re-run the price-CSV
import. If you do want to rebuild the station data from scratch (this
is also what regenerates the fixture itself, if the import logic ever
changes):

```bash
.venv/bin/python manage.py seed_fuel_stations \
  --prices fuel-prices-for-be-assessment.csv \
  --city-coords fuel/data/us_city_coords.csv \
  --clear
.venv/bin/python manage.py dumpdata fuel.FuelStation --indent 2 > fuel/fixtures/fuel_stations.json
```

## What's in the repo

- `config/` — Django settings and URL routing.
- `fuel/` — the app itself: `models.py` for the station table,
  `services/` for the actual logic (geocoding, routing, the DP
  planner, city search), `api_response.py` for the response shape
  every endpoint returns, and `views.py`/`urls.py` for the API.
- `templates/index.html` + `static/js/app.js` — the frontend.
- `fuel-prices-for-be-assessment.csv` — the price data given in the
  assignment.
- `fuel/data/us_city_coords.csv` — the city/state → lat/lon lookup
  used to geocode that price data offline.
- `fuel/fixtures/fuel_stations.json` — the already-seeded station
  table, so a fresh clone works without re-running the import.
- `Dockerfile`, `entrypoint.sh`, `.dockerignore` — the Docker build.
  The entrypoint runs migrations and loads the station fixture on
  every start (idempotent, so it's safe on a fresh empty database and
  a no-op if the data's already there), then starts `gunicorn`.

## API response shape

Every response from `/api/route/` and `/api/cities/` looks like this:

```jsonc
// on success
{"status": true, "status_code": 200, "message": "...", "data": {...}, "other": []}
// on error
{"status": false, "status_code": 400, "message": "...", "errors": []}
```

`data` holds the actual payload (route geometry, fuel stops, city
matches, whatever the endpoint returns). `message` is always a
human-readable summary. See `fuel/api_response.py`.

## Testing

```bash
.venv/bin/python manage.py test
```

59 tests. They cover the distance math, the GeoNames parsing and seed
command (including deduping a station listed at multiple prices down
to its cheapest), the DP planner (including a hand-traced multi-stop
case and the off-route detour cost), the corridor filter, city search,
the health endpoint, and the view's error handling, all against mocked
HTTP clients, so nothing here needs a live network connection to pass.
Separately, the app has also been exercised against the real
OSRM/Nominatim/Overpass services, against a real Postgres (Neon)
database, in a built Docker container, and in an actual browser, since
passing tests only proves the code does what the tests assume, not
that it works against the real world.

## Known limitations

A few source rows in the price CSV have trailing whitespace in the
city/name fields, inherited from the original assessment data; this
doesn't affect anything functionally, just cosmetic if you inspect the
raw values.

