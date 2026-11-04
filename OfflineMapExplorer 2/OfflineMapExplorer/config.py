"""OfflineMap Explorer Configuration
Defines paths, server ports, routing defaults, and application settings.
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "app"
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

MAPS_DIR = DATA_DIR / "maps"
TILES_DIR = DATA_DIR / "tiles"
ROUTES_DIR = DATA_DIR / "routes"
DB_PATH = DATA_DIR / "offlinemap.db"

# Ensure runtime directories exist
for directory in [DATA_DIR, MAPS_DIR, TILES_DIR, ROUTES_DIR, ASSETS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Application metadata
APP_NAME = "OfflineMap Explorer"
APP_VERSION = "1.0.0"
APP_ORGANIZATION = "OfflineMapProject"

# Server configuration for serving frontend & offline tiles
SERVER_HOST = "127.0.0.1"
SERVER_DEFAULT_PORT = 8765

# Tile and OSM upstream configuration
OSM_TILE_SERVERS = [
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
]
CARTO_DARK_SERVER = "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
CARTO_LIGHT_SERVER = "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
TOPO_SERVER = "https://tile.opentopomap.org/{z}/{x}/{y}.png"

USER_AGENT = f"OfflineMapExplorer/{APP_VERSION} (desktop offline navigation application)"

# Default map view (Central London / Westminster)
DEFAULT_LAT = 51.5074
DEFAULT_LNG = -0.1278
DEFAULT_ZOOM = 13

# Routing speed profiles in km/h
SPEED_PROFILES = {
    "driving": {
        "motorway": 100.0,
        "trunk": 80.0,
        "primary": 60.0,
        "secondary": 50.0,
        "tertiary": 40.0,
        "unclassified": 30.0,
        "residential": 30.0,
        "living_street": 15.0,
        "service": 15.0,
        "default": 40.0,
    },
    "walking": {
        "footway": 4.8,
        "path": 4.5,
        "pedestrian": 4.8,
        "steps": 2.5,
        "residential": 4.8,
        "service": 4.8,
        "default": 4.8,
    }
}

# Offline tile download presets for popular regions
PRESET_REGIONS = [
    {
        "id": "london_center",
        "name": "Central London, UK",
        "min_lat": 51.485,
        "min_lng": -0.165,
        "max_lat": 51.530,
        "max_lng": -0.075,
        "center": [51.5074, -0.1278],
        "zoom_levels": [12, 13, 14, 15]
    },
    {
        "id": "paris_center",
        "name": "Paris Center, France",
        "min_lat": 48.835,
        "min_lng": 2.290,
        "max_lat": 48.885,
        "max_lng": 2.380,
        "center": [48.8566, 2.3522],
        "zoom_levels": [12, 13, 14, 15]
    },
    {
        "id": "new_york_manhattan",
        "name": "Manhattan, New York, USA",
        "min_lat": 40.700,
        "min_lng": -74.020,
        "max_lat": 40.780,
        "max_lng": -73.940,
        "center": [40.7580, -73.9855],
        "zoom_levels": [12, 13, 14, 15]
    },
    {
        "id": "tokyo_shinjuku",
        "name": "Tokyo (Shinjuku / Shibuya), Japan",
        "min_lat": 35.650,
        "min_lng": 139.680,
        "max_lat": 35.710,
        "max_lng": 139.730,
        "center": [35.6895, 139.6917],
        "zoom_levels": [12, 13, 14, 15]
    },
    {
        "id": "san_francisco_downtown",
        "name": "San Francisco Downtown, USA",
        "min_lat": 37.760,
        "min_lng": -122.440,
        "max_lat": 37.810,
        "max_lng": -122.380,
        "center": [37.7749, -122.4194],
        "zoom_levels": [12, 13, 14, 15]
    }
]
