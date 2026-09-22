"""Django settings for config project. See .env.example for the values
below that come from the environment."""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes")


def env_float(name, default):
    return float(os.environ.get(name, default))


SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-eb!-&j$+_ik!$keyh5$99bl&g*shzaqd5$^bjd^muy-cmce(g^")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "fuel",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# DATABASE_URL (e.g. a Neon Postgres connection string) takes over when set;
# otherwise falls back to local SQLite so plain local dev needs no setup.
DATABASES = {
    "default": (
        dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600)
        if os.environ.get("DATABASE_URL")
        else {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    )
}

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Fuel Route API settings -- see .env.example to override any of these.

FUEL_MAX_RANGE_MILES = env_float("FUEL_MAX_RANGE_MILES", 500.0)
FUEL_MPG = env_float("FUEL_MPG", 10.0)
FUEL_CORRIDOR_MILES = env_float("FUEL_CORRIDOR_MILES", 5.0)

# Once a station is found this close to a sampled route point, it's clearly
# right on the route -- stop scanning remaining points for it early.
FUEL_CLEARLY_ON_ROUTE_MILES = env_float("FUEL_CLEARLY_ON_ROUTE_MILES", 0.1)

# Candidate-station search tuning (fuel/services/stations.py).
FUEL_MILES_PER_DEGREE_LAT = env_float("FUEL_MILES_PER_DEGREE_LAT", 69.0)
FUEL_SAMPLE_SPACING_MILES = env_float("FUEL_SAMPLE_SPACING_MILES", 1.0)

# Used only when no priced station is found near the route at all, so
# total_cost is never $0 for a real trip.
FUEL_DEFAULT_PRICE_PER_GALLON = env_float("FUEL_DEFAULT_PRICE_PER_GALLON", 3.43)

OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "http://router.project-osrm.org")
NOMINATIM_BASE_URL = os.environ.get("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
EXTERNAL_API_TIMEOUT_SECONDS = env_float("EXTERNAL_API_TIMEOUT_SECONDS", 8)

# Optional local classic-A* engine (fuel/services/local_astar.py), capped
# to short routes -- see that file for why.
LOCAL_ASTAR_MAX_MILES = env_float("LOCAL_ASTAR_MAX_MILES", 50.0)
