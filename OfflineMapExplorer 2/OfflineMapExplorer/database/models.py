"""Data models for OfflineMap Explorer
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class Region:
    id: str
    name: str
    min_lat: float
    min_lng: float
    max_lat: float
    max_lng: float
    min_zoom: int
    max_zoom: int
    tile_count: int = 0
    size_bytes: int = 0
    created_at: str = ""
    status: str = "completed"  # 'downloading', 'completed', 'error'
    has_routing: bool = False

    @property
    def center(self) -> tuple[float, float]:
        return ((self.min_lat + self.max_lat) / 2.0, (self.min_lng + self.max_lng) / 2.0)

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.min_lat, self.min_lng, self.max_lat, self.max_lng)

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)


@dataclass
class Bookmark:
    id: Optional[int]
    name: str
    category: str  # 'Home', 'Work', 'Favorite', 'Landmark', 'Restaurant'
    lat: float
    lng: float
    address: str = ""
    created_at: str = ""


@dataclass
class NavigationHistoryItem:
    id: Optional[int]
    start_name: str
    start_lat: float
    start_lng: float
    dest_name: str
    dest_lat: float
    dest_lng: float
    mode: str  # 'driving', 'walking'
    distance_km: float
    duration_min: float
    created_at: str = ""


@dataclass
class POI:
    id: Optional[int]
    name: str
    category: str
    street: str
    city: str
    lat: float
    lng: float
    region_id: str = ""
