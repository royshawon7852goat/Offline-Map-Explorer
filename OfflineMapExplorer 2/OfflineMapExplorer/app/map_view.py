"""Map View Widget for OfflineMap Explorer
Integrates PySide6 QtWebEngineView with Leaflet map via QWebChannel bridge.
"""

import json
import logging
from PySide6.QtCore import QObject, Signal, Slot, QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebChannel import QWebChannel

logger = logging.getLogger("OfflineMap.MapView")

class MapBridge(QObject):
    """Bridge object exposed to JavaScript window.mapBridge"""
    mapClicked = Signal(float, float)
    regionSelected = Signal(float, float, float, float)
    navigationPointSet = Signal(str, float, float, str)
    bookmarkRequested = Signal(float, float, str)
    currentLocationRequested = Signal()
    layerChanged = Signal(str)
    mapMoved = Signal(float, float, int)
    mapReady = Signal()

    @Slot()
    def onMapReady(self):
        logger.info("Leaflet map initialized and bridge connected.")
        self.mapReady.emit()

    @Slot(float, float)
    def onMapClicked(self, lat: float, lng: float):
        self.mapClicked.emit(lat, lng)

    @Slot(float, float, float, float)
    def onRegionSelected(self, min_lat: float, min_lng: float, max_lat: float, max_lng: float):
        self.regionSelected.emit(min_lat, min_lng, max_lat, max_lng)

    @Slot(str, float, float, str)
    def setNavigationPoint(self, point_type: str, lat: float, lng: float, name: str):
        self.navigationPointSet.emit(point_type, lat, lng, name)

    @Slot(float, float, str)
    def saveBookmarkFromMap(self, lat: float, lng: float, name: str):
        self.bookmarkRequested.emit(lat, lng, name)

    @Slot()
    def onRequestCurrentLocation(self):
        self.currentLocationRequested.emit()

    @Slot(str)
    def onLayerChanged(self, layer_id: str):
        self.layerChanged.emit(layer_id)

    @Slot(float, float, int)
    def onMapMoved(self, center_lat: float, center_lng: float, zoom: int):
        self.mapMoved.emit(center_lat, center_lng, zoom)


class MapView(QWidget):
    """Container widget housing QWebEngineView and bridge methods."""
    def __init__(self, server_port: int, parent=None):
        super().__init__(parent)
        self.server_port = server_port
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # WebEngine View
        self.web_view = QWebEngineView(self)
        self.layout.addWidget(self.web_view)

        # Settings
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)

        # Setup WebChannel
        self.channel = QWebChannel(self.web_view.page())
        self.bridge = MapBridge()
        self.channel.registerObject("mapBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Load Leaflet map from local server
        url = QUrl(f"http://127.0.0.1:{self.server_port}/index.html")
        self.web_view.load(url)

    def run_js(self, script: str):
        """Executes JavaScript code in the Leaflet map context."""
        self.web_view.page().runJavaScript(script)

    def set_theme(self, is_dark: bool):
        val = "true" if is_dark else "false"
        self.run_js(f"window.setTheme({val});")

    def set_offline_status(self, is_offline: bool):
        val = "true" if is_offline else "false"
        self.run_js(f"window.setOfflineStatus({val});")

    def fly_to(self, lat: float, lng: float, zoom: int = 15):
        self.run_js(f"window.flyTo({lat}, {lng}, {zoom});")

    def fit_bounds(self, min_lat: float, min_lng: float, max_lat: float, max_lng: float):
        self.run_js(f"window.fitBounds({min_lat}, {min_lng}, {max_lat}, {max_lng});")

    def show_location_pin(self, lat: float, lng: float, title: str, subtitle: str = ""):
        title_esc = title.replace("'", "\\'")
        sub_esc = subtitle.replace("'", "\\'")
        self.run_js(f"window.showLocationPin({lat}, {lng}, '{title_esc}', '{sub_esc}');")

    def display_route(self, primary_coords: list, alt_coords: list = None, turn_steps: list = None):
        prim_json = json.dumps(primary_coords)
        alt_json = json.dumps(alt_coords or [])
        steps_json = json.dumps(turn_steps or [])
        self.run_js(f"window.displayRoute({prim_json}, {alt_json}, {steps_json});")

    def clear_route(self):
        self.run_js("window.clearRoute();")

    def update_gps(self, lat: float, lng: float, heading: float = 0.0, accuracy: float = 10.0):
        self.run_js(f"window.updateGpsPosition({lat}, {lng}, {heading}, {accuracy});")

    def highlight_regions(self, regions: list):
        data = [
            {
                "id": r.id,
                "name": r.name,
                "min_lat": r.min_lat,
                "min_lng": r.min_lng,
                "max_lat": r.max_lat,
                "max_lng": r.max_lng,
                "size_mb": r.size_mb
            }
            for r in regions
        ]
        reg_json = json.dumps(data)
        self.run_js(f"window.highlightDownloadedRegions({reg_json});")

    def start_region_selection(self):
        self.run_js("window.startRegionSelectionMode();")
