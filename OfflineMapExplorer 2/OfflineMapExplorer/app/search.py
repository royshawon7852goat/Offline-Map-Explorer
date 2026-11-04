"""Location Search Engine for OfflineMap Explorer
Combines SQLite FTS5 offline indexed POIs/streets with online Nominatim fallback,
caching all online geocoded results locally for future offline search.
"""

import json
import logging
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from PySide6.QtCore import QObject, QThread, Signal

from config import USER_AGENT
from database.database import Database
from database.models import POI

logger = logging.getLogger("OfflineMap.Search")

class SearchWorker(QThread):
    """Background worker thread for non-blocking search and suggestion queries."""
    resultsReady = Signal(list)
    searchError = Signal(str)

    def __init__(self, db: Database, query: str, is_offline_mode: bool, parent=None):
        super().__init__(parent)
        self.db = db
        self.query = query.strip()
        self.is_offline_mode = is_offline_mode
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not self.query or len(self.query) < 2:
            self.resultsReady.emit([])
            return

        combined_results: List[Dict[str, Any]] = []
        seen_keys = set()

        # 1. Search Bookmarks first (highest priority)
        bookmarks = self.db.get_bookmarks()
        q_lower = self.query.lower()
        for b in bookmarks:
            if q_lower in b.name.lower() or q_lower in b.address.lower():
                key = (round(b.lat, 4), round(b.lng, 4))
                if key not in seen_keys:
                    seen_keys.add(key)
                    combined_results.append({
                        "name": b.name,
                        "category": f"Bookmark ({b.category})",
                        "street": b.address,
                        "city": "",
                        "lat": b.lat,
                        "lng": b.lng,
                        "source": "bookmark"
                    })

        # 2. Search local offline database (FTS5 indexed POIs, roads, landmarks)
        offline_matches = self.db.search_pois(self.query, limit=20)
        for m in offline_matches:
            key = (round(m["lat"], 4), round(m["lng"], 4))
            if key not in seen_keys:
                seen_keys.add(key)
                combined_results.append({
                    "name": m["name"],
                    "category": m.get("category", "Place"),
                    "street": m.get("street", ""),
                    "city": m.get("city", ""),
                    "lat": m["lat"],
                    "lng": m["lng"],
                    "source": "offline_db"
                })

        # 3. If online mode allowed and we have few local results, query Nominatim
        if not self.is_offline_mode and not self._is_cancelled and len(combined_results) < 5:
            try:
                online_pois = self._fetch_nominatim(self.query)
                for op in online_pois:
                    if self._is_cancelled:
                        break
                    key = (round(op["lat"], 4), round(op["lng"], 4))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        combined_results.append(op)
                        # Save to offline database so it's cached forever
                        self.db.insert_pois_batch([
                            POI(
                                id=None,
                                name=op["name"],
                                category=op["category"],
                                street=op.get("street", ""),
                                city=op.get("city", ""),
                                lat=op["lat"],
                                lng=op["lng"],
                                region_id="cached_search"
                            )
                        ])
            except Exception as e:
                logger.debug(f"Online Nominatim query skipped/failed: {e}")

        if not self._is_cancelled:
            self.resultsReady.emit(combined_results[:25])

    def _fetch_nominatim(self, query: str) -> List[Dict[str, Any]]:
        """Queries OpenStreetMap Nominatim geocoder."""
        params = {
            "q": query,
            "format": "json",
            "addressdetails": "1",
            "limit": "10"
        }
        url = f"https://nominatim.openstreetmap.org/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for item in data:
            lat = float(item["lat"])
            lon = float(item["lon"])
            disp_name = item.get("display_name", "")
            name_parts = disp_name.split(",")
            title = name_parts[0].strip()
            addr = item.get("address", {})
            street = addr.get("road") or addr.get("pedestrian") or ""
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county") or ""
            category = item.get("type", "Place").capitalize()

            results.append({
                "name": title,
                "category": category,
                "street": street,
                "city": city,
                "lat": lat,
                "lng": lon,
                "source": "online"
            })
        return results


class SearchController(QObject):
    """Coordinates search UI input, debounce, and worker lifecycle."""
    searchResultsUpdated = Signal(list)
    searchStarted = Signal()
    searchFailed = Signal(str)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.is_offline_mode = False
        self.active_worker: Optional[SearchWorker] = None

    def set_offline_mode(self, is_offline: bool):
        self.is_offline_mode = is_offline

    def execute_search(self, query: str):
        if self.active_worker and self.active_worker.isRunning():
            self.active_worker.cancel()
            self.active_worker.wait()

        self.searchStarted.emit()
        self.active_worker = SearchWorker(self.db, query, self.is_offline_mode)
        self.active_worker.resultsReady.connect(self.searchResultsUpdated)
        self.active_worker.searchError.connect(self.searchFailed)
        self.active_worker.start()
