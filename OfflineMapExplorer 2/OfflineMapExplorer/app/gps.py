"""GPS Position Tracking and Route Navigation Simulator for OfflineMap Explorer
Supports real-time GPS simulation, route turn guidance tracking, speed calculation,
and compass heading interpolation.
"""

import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from PySide6.QtCore import QObject, QTimer, Signal

from routing.directions import calculate_haversine_distance, calculate_bearing

logger = logging.getLogger("OfflineMap.GPS")

class GPSSimulator(QObject):
    """Simulates live GPS navigation updates along a route polyline."""
    locationUpdated = Signal(float, float, float, float, float)  # lat, lng, heading, speed_kmh, accuracy
    stepProgress = Signal(int, float)  # current_step_index, distance_to_next_turn_m
    destinationReached = Signal()
    gpsStatusChanged = Signal(str)  # 'locked', 'simulating', 'idle'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer_interval_ms = 400  # 2.5 updates per second

        self.current_lat: float = 51.5074
        self.current_lng: float = -0.1278
        self.current_heading: float = 0.0
        self.current_speed_kmh: float = 0.0
        self.is_simulating: bool = False

        # Route simulation state
        self.route_coords: List[List[float]] = []
        self.turn_steps: List[Dict[str, Any]] = []
        self.coord_index: int = 0
        self.step_index: int = 0
        self.speed_multiplier: float = 1.0

    def set_current_position(self, lat: float, lng: float, heading: float = 0.0):
        self.current_lat = lat
        self.current_lng = lng
        self.current_heading = heading
        self.current_speed_kmh = 0.0
        self.locationUpdated.emit(self.current_lat, self.current_lng, self.current_heading, 0.0, 5.0)

    def start_navigation_simulation(self, route_coords: List[List[float]], turn_steps: List[Dict[str, Any]], speed_multiplier: float = 2.0):
        """Starts animated navigation along route coordinates."""
        if not route_coords or len(route_coords) < 2:
            return

        self.route_coords = route_coords
        self.turn_steps = turn_steps or []
        self.coord_index = 0
        self.step_index = 0
        self.speed_multiplier = speed_multiplier
        self.is_simulating = True

        # Snap to start
        self.current_lat = route_coords[0][0]
        self.current_lng = route_coords[0][1]
        self.current_heading = calculate_bearing(
            route_coords[0][0], route_coords[0][1],
            route_coords[1][0], route_coords[1][1]
        )
        self.current_speed_kmh = 45.0

        self.gpsStatusChanged.emit("simulating")
        self.timer.start(self.timer_interval_ms)
        self.locationUpdated.emit(self.current_lat, self.current_lng, self.current_heading, self.current_speed_kmh, 3.0)

    def stop_simulation(self):
        if self.timer.isActive():
            self.timer.stop()
        self.is_simulating = False
        self.current_speed_kmh = 0.0
        self.gpsStatusChanged.emit("idle")

    def _on_tick(self):
        if not self.is_simulating or self.coord_index >= len(self.route_coords) - 1:
            self.stop_simulation()
            self.destinationReached.emit()
            return

        self.coord_index += 1
        pt = self.route_coords[self.coord_index]
        prev_lat, prev_lng = self.current_lat, self.current_lng
        self.current_lat = pt[0]
        self.current_lng = pt[1]

        # Calculate live heading and speed
        dist_m = calculate_haversine_distance(prev_lat, prev_lng, self.current_lat, self.current_lng)
        self.current_heading = calculate_bearing(prev_lat, prev_lng, self.current_lat, self.current_lng)
        self.current_speed_kmh = round((dist_m / (self.timer_interval_ms / 1000.0)) * 3.6, 1)

        # Determine proximity to upcoming turn step
        if self.step_index < len(self.turn_steps):
            next_step = self.turn_steps[self.step_index]
            step_lat = next_step.get("lat", 0.0)
            step_lng = next_step.get("lng", 0.0)
            dist_to_step = calculate_haversine_distance(self.current_lat, self.current_lng, step_lat, step_lng)

            # Advance to next turn step if close (< 30 meters)
            if dist_to_step < 30.0 and self.step_index < len(self.turn_steps) - 1:
                self.step_index += 1

            self.stepProgress.emit(self.step_index, dist_to_step)

        self.locationUpdated.emit(
            self.current_lat, self.current_lng, self.current_heading, self.current_speed_kmh, 3.0
        )
