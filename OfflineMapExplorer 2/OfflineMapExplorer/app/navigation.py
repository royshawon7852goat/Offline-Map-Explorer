"""Navigation Controller and Turn-by-Turn Panel for OfflineMap Explorer
Manages route requests, start/dest coordinates, travel mode, and navigation HUD.
"""

from typing import List, Dict, Any, Optional
from PySide6.QtCore import QObject, Signal

from database.database import Database
from database.models import NavigationHistoryItem
from routing.route_engine import OfflineRouteEngine

class NavigationController(QObject):
    routeCalculated = Signal(dict)  # route result dict
    routeCleared = Signal()
    routeError = Signal(str)
    navigationStarted = Signal(list, list)  # coords, turn_steps
    navigationStopped = Signal()

    def __init__(self, db: Database, route_engine: OfflineRouteEngine, parent=None):
        super().__init__(parent)
        self.db = db
        self.route_engine = route_engine

        self.start_point: Optional[Dict[str, Any]] = None  # {'name': str, 'lat': float, 'lng': float}
        self.dest_point: Optional[Dict[str, Any]] = None
        self.travel_mode: str = "driving"  # 'driving' or 'walking'
        self.current_route_data: Optional[Dict[str, Any]] = None

    def set_start(self, lat: float, lng: float, name: str):
        self.start_point = {"name": name, "lat": lat, "lng": lng}

    def set_destination(self, lat: float, lng: float, name: str):
        self.dest_point = {"name": name, "lat": lat, "lng": lng}

    def swap_endpoints(self):
        self.start_point, self.dest_point = self.dest_point, self.start_point

    def set_mode(self, mode: str):
        self.travel_mode = mode

    def calculate_route(self) -> Optional[Dict[str, Any]]:
        if not self.start_point or not self.dest_point:
            self.routeError.emit("Please select both a starting location and a destination.")
            return None

        res = self.route_engine.calculate_route(
            start_lat=self.start_point["lat"],
            start_lng=self.start_point["lng"],
            dest_lat=self.dest_point["lat"],
            dest_lng=self.dest_point["lng"],
            mode=self.travel_mode,
            find_alternatives=True
        )

        if res.get("status") == "error":
            self.routeError.emit(res.get("message", "Route calculation failed."))
            return None

        self.current_route_data = res

        # Save to navigation history in SQLite
        primary = res.get("primary_route", {})
        dist_km = round(primary.get("distance_m", 0) / 1000.0, 2)
        dur_min = round(primary.get("duration_s", 0) / 60.0, 1)

        history_item = NavigationHistoryItem(
            id=None,
            start_name=self.start_point["name"],
            start_lat=self.start_point["lat"],
            start_lng=self.start_point["lng"],
            dest_name=self.dest_point["name"],
            dest_lat=self.dest_point["lat"],
            dest_lng=self.dest_point["lng"],
            mode=self.travel_mode,
            distance_km=dist_km,
            duration_min=dur_min
        )
        self.db.add_history(history_item)

        self.routeCalculated.emit(res)
        return res

    def clear(self):
        self.current_route_data = None
        self.routeCleared.emit()
