# OfflineMap Explorer

**OfflineMap Explorer** is a complete, production-grade desktop application for offline geographical exploration, location search, and turn-by-turn navigation without requiring an internet connection.

Built with **Python 3.12+ / 3.14**, **PySide6 (Qt6)**, **Qt WebEngine**, **Leaflet.js**, **SQLite (with FTS5 Full-Text Search)**, **NetworkX**, and **Shapely**, it implements a Google Maps-inspired desktop experience capable of functioning 100% offline once map data is downloaded or cached.

---

## 🌟 Key Features

### 1. Interactive Desktop Map
* **Pan, Zoom, and Smooth Navigation**: Responsive canvas powered by Leaflet.js inside PySide6 QtWebEngine.
* **Dual Theme Engine**: Seamless switching between **Light** and **Dark Mode**, including dark map styling.
* **Layer Switcher**: Toggle between Standard OpenStreetMap, Carto Light, Carto Dark, and Local Offline Storage.
* **Scale & Compass**: Metric scale indicator and one-click North orientation reset.

### 2. Offline Map Downloads & Region Management
* **Interactive Bounding Box Selection**: Draw a custom rectangular bounding box directly on the map to define any geographical area for offline download.
* **1-Click City Presets**: Preconfigured regions ready for immediate download (Central London, Manhattan NY, Paris Center, Tokyo, San Francisco).
* **Multi-Zoom Download Engine**: Automatically computes and fetches tile hierarchies (zooms 12–15) with background worker threads and real-time progress reporting.
* **Persistent Offline Storage**: All downloaded tiles, road geometries, and POIs are stored locally in SQLite (`data/offlinemap.db`).
* **Region Inspection & Deletion**: View downloaded regions, see disk consumption (MB), highlight region boundaries on the map, and remove regions when needed.

### 3. High-Performance Offline Search
* **SQLite FTS5 Full-Text Search**: Instant search suggestions and autocomplete for streets, POIs, landmarks, and cities without internet access.
* **Bookmark Priority**: Saved places are automatically queried first and displayed at the top of search suggestions.
* **Online Fallback & Auto-Cache**: When online mode is enabled, queries Nominatim for unknown locations and automatically caches the resulting coordinates and POIs into the local SQLite database for future offline queries.

### 4. True Offline Routing Engine
* **A\* Pathfinding with NetworkX**: Road network graph with Haversine distance heuristics for shortest and fastest route calculations.
* **Driving & Walking Modes**:
  * **Driving**: Accounts for road hierarchy (`motorway`, `trunk`, `primary`, `secondary`, `residential`), one-way restrictions, and real travel speeds.
  * **Walking**: Direct access through footways, paths, pedestrian precincts, and bi-directional traversal.
* **Alternative Route Discovery**: Evaluates secondary viable paths using edge-penalty factors.
* **Detailed Turn-by-Turn Instructions**: Calculates bearing changes at junctions to generate human-readable turn guidance (*"Head North on Main St"*, *"Turn right onto Strand in 350m"*, *"Slight left onto Whitehall"*).

### 5. GPS Tracking & Navigation HUD
* **Real-time Navigation Simulator**: When *"Start Navigation"* is clicked, the GPS engine simulates live vehicle/pedestrian movement along the route coordinates.
* **Live Heading & Speed**: Dynamically computes compass heading and real-time speed in km/h.
* **Proximity Turn Detection**: Automatically advances to upcoming turns as the user moves within 30 meters of a junction.
* **Bottom Navigation HUD**: Clean card displaying next maneuver icon, distance to next turn, total trip distance, estimated time of arrival (ETA), and simulation controls.

### 6. Saved Places (Bookmarks)
* **Persistent SQLite Bookmarks**: Save custom locations directly from the map or search results.
* **Categorization**: Tag bookmarks as *Home*, *Work*, *Favorite*, *Landmark*, or *Restaurant*.
* **1-Click Navigation**: Instantly set any bookmark as a route destination or origin.

### 7. Guaranteed Offline Integrity
* **Force Offline Mode Switch**: Toggle on *"Force Offline-Only Mode"* in Settings to block all network calls.
* **Pre-bundled Starter Data**: Includes an out-of-the-box offline road network and POI index for Central London and Manhattan so the application is immediately testable and functional offline upon initial launch!

---

## 🏗️ Architecture & Project Structure

```
OfflineMapExplorer/
│
├── main.py                    # Application bootstrap & Qt event loop
├── config.py                  # Global settings, paths, server ports, presets
├── requirements.txt           # Python dependencies
├── README.md                  # Detailed documentation
│
├── app/
│   ├── __init__.py
│   ├── main_window.py         # Google Maps-style UI: Rail, Sidebar, Map, HUD
│   ├── map_view.py            # QWebEngineView with QWebChannel bridge
│   ├── tile_server.py         # Local HTTP proxy & SQLite tile cache server
│   ├── search.py              # Offline FTS5 search & Nominatim geocoder
│   ├── downloads.py           # Tile downloader & Overpass OSM road extractor
│   ├── navigation.py          # Route controller & history manager
│   ├── gps.py                 # GPS simulator & turn step tracker
│   └── settings.py            # App settings (theme, offline toggle, cache)
│
├── database/
│   ├── __init__.py
│   ├── database.py            # SQLite schema (tiles, pois, regions, roads, bookmarks)
│   └── models.py              # Python dataclasses (Region, Bookmark, POI)
│
├── routing/
│   ├── __init__.py
│   ├── route_engine.py        # NetworkX A* graph pathfinder & STRtree index
│   └── directions.py          # Maneuver classifier & turn instructions generator
│
├── frontend/
│   ├── index.html             # Leaflet map viewport HTML
│   ├── style.css              # Light/Dark CSS, HUD overlays, popup cards
│   ├── map.js                 # Leaflet controller & Python bridge integration
│   ├── qwebchannel.js         # Qt WebChannel JavaScript runtime
│   └── leaflet/               # Bundled local Leaflet 1.9.4 assets (100% offline)
│       ├── leaflet.js
│       ├── leaflet.css
│       └── images/
│
├── data/
│   ├── offlinemap.db          # Local SQLite database
│   ├── maps/                  # Offline map bundles
│   ├── tiles/                 # Disk tile storage
│   └── routes/                # Exported routes (GPX/GeoJSON)
│
├── assets/
│   └── icons/                 # UI assets
│
└── tests/
    ├── test_core.py           # Headless unit tests for DB, routing, and search
    └── test_gui.py            # GUI smoke test verifying PySide6 & WebEngine
```

---

## 💻 Installation

### Prerequisites
* **Python 3.12+** (compatible with Python 3.12, 3.13, and 3.14 on Windows, Linux, and macOS).
* **pip** package installer.

### 1. Install Dependencies
In your terminal or PowerShell:
```bash
pip install -r requirements.txt
```

Core libraries installed:
* `PySide6` (GUI framework and WebEngine)
* `networkx` (Road network graph modeling & A* pathfinding)
* `shapely` (Spatial geometries and STRtree fast nearest-neighbor snapping)
* `geopandas` (Geospatial data structures)
* `requests` (Network fetching for map downloads)
* `Pillow` (Offline tile image synthesis)

---

## 🚀 Running the Application

### Running from Terminal / PowerShell
Navigate to the project root directory and execute:
```bash
python main.py
```

### Running in VS Code
1. Open VS Code:
   ```bash
   code C:\Users\roysh\.gemini\antigravity\scratch\OfflineMapExplorer
   ```
2. Select your Python interpreter (`Ctrl + Shift + P` -> `Python: Select Interpreter`).
3. Open `main.py` and click the **Run Python File** button (or press `F5`).

---

## 🧪 Running the Automated Tests

The application includes automated test suites:

### 1. Backend Core & Routing Unit Tests
Validates SQLite database initialization, FTS5 full-text search, NetworkX A* routing, turn instructions, walking/driving modes, and tile proxy:
```bash
python tests/test_core.py
```

### 2. GUI Smoke & WebEngine Integration Test
Launches the full PySide6 interface, tests navigation rail tabs, search inputs, dark mode toggling, offline mode enforcement, and closes cleanly:
```bash
python tests/test_gui.py
```

---

## 📖 User Guide

### How to Calculate an Offline Route
1. Click the **🧭 Directions** tab on the left rail.
2. Select **🚗 Driving** or **🚶 Walking** mode.
3. Click any point on the map to show the action popup:
   * Click **[Directions From]** to set the start.
   * Click another location and choose **[Directions To]** to set the destination.
4. Click **"Find Offline Route"**.
5. The route polyline and turn steps will be rendered on the map and listed in the sidebar.
6. The **Bottom Navigation HUD** will slide up with trip metrics. Click **"▶ Start Navigation"** to watch the simulated GPS vehicle navigate turn-by-turn!

### How to Download a Region for Offline Use
1. Click the **📥 Offline Maps** tab on the left rail.
2. Choose either:
   * **1-Click Preset**: Select a city (e.g. *Central London*, *Manhattan*, *Paris Center*) and click **"Download"**.
   * **Custom Area**: Click **"📐 Select Region on Map"**, then click and drag a rectangle over the desired area on the map.
3. The background worker downloads the raster tiles and extracts road networks and POIs into SQLite.
4. The region will be outlined in green on the map and permanently available offline.

### How to Test 100% Offline Mode
1. Click the **⚙️ Settings** tab.
2. Check the box **"Force Offline-Only Mode"**.
3. All external network requests are immediately severed.
4. Search for places, browse downloaded regions, and compute driving/walking routes—everything functions completely offline!
