"""Main Window for OfflineMap Explorer
Features Google Maps-inspired layout:
- Left Navigation Rail with collapsible Sidebar panels (Search, Navigation, Offline Maps, Saved, Settings)
- Central Interactive Map Viewport with floating HUD controls
- Bottom Navigation Turn-by-Turn Guidance HUD
- Dark & Light theme styling
"""

import logging
from typing import Optional, Dict, Any, List
from PySide6.QtCore import Qt, QSize, Slot, QTimer
from PySide6.QtGui import QIcon, QFont, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QCheckBox, QComboBox, QFrame, QScrollArea,
    QMessageBox, QInputDialog, QSplitter, QButtonGroup
)

from config import APP_NAME, APP_VERSION, PRESET_REGIONS
from database.database import Database
from database.models import Bookmark, Region
from routing.route_engine import OfflineRouteEngine
from app.map_view import MapView
from app.tile_server import LocalTileServer
from app.search import SearchController
from app.downloads import DownloadWorker
from app.navigation import NavigationController
from app.gps import GPSSimulator
from app.settings import SettingsManager

logger = logging.getLogger("OfflineMap.MainWindow")

class MainWindow(QMainWindow):
    def __init__(self, db: Database, tile_server: LocalTileServer):
        super().__init__()
        self.db = db
        self.tile_server = tile_server

        # Subsystems
        self.settings = SettingsManager(self.db)
        self.route_engine = OfflineRouteEngine(self.db)
        self.nav_controller = NavigationController(self.db, self.route_engine)
        self.search_controller = SearchController(self.db)
        self.gps_sim = GPSSimulator()
        self.active_download_worker: Optional[DownloadWorker] = None

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} - Offline Navigation")
        self.resize(1200, 800)
        self.setMinimumSize(950, 600)

        self._init_ui()
        self._wire_signals()
        self._apply_theme(self.settings.is_dark)

        # Refresh downloaded regions on map after ready
        QTimer.singleShot(1500, self._initial_sync)

    def _init_ui(self):
        # Central Container with Splitter
        self.main_container = QWidget(self)
        self.setCentralWidget(self.main_container)
        self.root_layout = QHBoxLayout(self.main_container)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # 1. Left Icon Rail (60px wide)
        self.rail = QWidget(self)
        self.rail.setObjectName("NavRail")
        self.rail.setFixedWidth(64)
        self.rail_layout = QVBoxLayout(self.rail)
        self.rail_layout.setContentsMargins(8, 12, 8, 12)
        self.rail_layout.setSpacing(12)

        self.rail_btn_group = QButtonGroup(self)
        self.rail_btn_group.setExclusive(True)

        self.btn_tab_search = self._create_rail_btn("🔍", "Search", 0)
        self.btn_tab_nav = self._create_rail_btn("🧭", "Directions", 1)
        self.btn_tab_downloads = self._create_rail_btn("📥", "Offline Maps", 2)
        self.btn_tab_bookmarks = self._create_rail_btn("⭐", "Saved Places", 3)
        self.btn_tab_settings = self._create_rail_btn("⚙️", "Settings", 4)

        self.rail_layout.addStretch()

        # 2. Sidebar Panel (Stacked Widget)
        self.sidebar_stack = QStackedWidget(self)
        self.sidebar_stack.setFixedWidth(340)
        self.sidebar_stack.setObjectName("SidebarPanel")

        self.page_search = self._create_search_page()
        self.page_nav = self._create_nav_page()
        self.page_downloads = self._create_downloads_page()
        self.page_bookmarks = self._create_bookmarks_page()
        self.page_settings = self._create_settings_page()

        self.sidebar_stack.addWidget(self.page_search)
        self.sidebar_stack.addWidget(self.page_nav)
        self.sidebar_stack.addWidget(self.page_downloads)
        self.sidebar_stack.addWidget(self.page_bookmarks)
        self.sidebar_stack.addWidget(self.page_settings)

        # 3. Right Area (Map Viewport + Floating Bottom HUD)
        self.right_container = QWidget(self)
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(0)

        # Map View
        self.map_view = MapView(self.tile_server.port, self)
        self.right_layout.addWidget(self.map_view, 1)

        # Bottom Turn-by-Turn Navigation HUD (Collapsible)
        self.nav_hud = self._create_nav_hud()
        self.nav_hud.setVisible(False)
        self.right_layout.addWidget(self.nav_hud)

        # Assemble Root Layout
        self.root_layout.addWidget(self.rail)
        self.root_layout.addWidget(self.sidebar_stack)
        self.root_layout.addWidget(self.right_container, 1)

        # Default Tab
        self.btn_tab_search.setChecked(True)
        self.sidebar_stack.setCurrentIndex(0)

    def _create_rail_btn(self, icon_text: str, tooltip: str, index: int) -> QPushButton:
        btn = QPushButton(icon_text, self.rail)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setFixedSize(48, 48)
        btn.setFont(QFont("Segoe UI Emoji", 16))
        btn.setObjectName(f"RailBtn_{index}")
        self.rail_btn_group.addButton(btn, index)
        self.rail_layout.addWidget(btn)
        btn.clicked.connect(lambda: self.sidebar_stack.setCurrentIndex(index))
        return btn

    # ==========================
    # Page 1: Search UI
    # ==========================
    def _create_search_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Explore & Search")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Search Bar
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Search streets, landmarks, cities...")
        self.input_search.setClearButtonEnabled(True)
        layout.addWidget(self.input_search)

        # Category Chips
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)
        for cat in ["All", "Landmark", "Transit", "Food"]:
            btn = QPushButton(cat)
            btn.setObjectName("ChipBtn")
            btn.clicked.connect(lambda _, c=cat: self._on_chip_clicked(c))
            chips_layout.addWidget(btn)
        layout.addLayout(chips_layout)

        # Search Results List
        self.list_search_results = QListWidget()
        self.list_search_results.setObjectName("SearchResultsList")
        layout.addWidget(self.list_search_results, 1)

        return page

    # ==========================
    # Page 2: Directions / Nav UI
    # ==========================
    def _create_nav_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Directions & Routing")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Mode Selector (Driving vs Walking)
        mode_layout = QHBoxLayout()
        self.btn_mode_driving = QPushButton("🚗 Driving")
        self.btn_mode_driving.setCheckable(True)
        self.btn_mode_driving.setChecked(True)
        self.btn_mode_walking = QPushButton("🚶 Walking")
        self.btn_mode_walking.setCheckable(True)

        mode_group = QButtonGroup(self)
        mode_group.addButton(self.btn_mode_driving)
        mode_group.addButton(self.btn_mode_walking)

        self.btn_mode_driving.clicked.connect(lambda: self.nav_controller.set_mode("driving"))
        self.btn_mode_walking.clicked.connect(lambda: self.nav_controller.set_mode("walking"))

        mode_layout.addWidget(self.btn_mode_driving)
        mode_layout.addWidget(self.btn_mode_walking)
        layout.addLayout(mode_layout)

        # Start and Destination Inputs
        endpoints_box = QFrame()
        endpoints_box.setObjectName("EndpointsCard")
        ep_layout = QVBoxLayout(endpoints_box)
        ep_layout.setContentsMargins(10, 10, 10, 10)
        ep_layout.setSpacing(8)

        # Start input
        start_row = QHBoxLayout()
        start_lbl = QLabel("A")
        start_lbl.setObjectName("EndpointBadgeA")
        self.input_start = QLineEdit()
        self.input_start.setPlaceholderText("Starting location (or click map)")
        self.input_start.setReadOnly(True)
        start_row.addWidget(start_lbl)
        start_row.addWidget(self.input_start)
        ep_layout.addLayout(start_row)

        # Destination input
        dest_row = QHBoxLayout()
        dest_lbl = QLabel("B")
        dest_lbl.setObjectName("EndpointBadgeB")
        self.input_dest = QLineEdit()
        self.input_dest.setPlaceholderText("Destination (or click map)")
        self.input_dest.setReadOnly(True)
        dest_row.addWidget(dest_lbl)
        dest_row.addWidget(self.input_dest)
        ep_layout.addLayout(dest_row)

        # Swap & Clear buttons
        act_row = QHBoxLayout()
        btn_swap = QPushButton("⇅ Swap")
        btn_swap.clicked.connect(self._swap_nav_endpoints)
        btn_clear = QPushButton("✕ Clear")
        btn_clear.clicked.connect(self._clear_navigation)
        act_row.addWidget(btn_swap)
        act_row.addWidget(btn_clear)
        ep_layout.addLayout(act_row)

        layout.addWidget(endpoints_box)

        # Calculate Route Button
        self.btn_calc_route = QPushButton("Find Offline Route")
        self.btn_calc_route.setObjectName("PrimaryBtn")
        self.btn_calc_route.clicked.connect(self._on_calculate_route)
        layout.addWidget(self.btn_calc_route)

        # Turn-by-Turn Instruction List
        lbl_steps = QLabel("Route Steps:")
        lbl_steps.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(lbl_steps)

        self.list_nav_steps = QListWidget()
        self.list_nav_steps.setObjectName("NavStepsList")
        layout.addWidget(self.list_nav_steps, 1)

        return page

    # ==========================
    # Page 3: Offline Maps Downloads UI
    # ==========================
    def _create_downloads_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Offline Maps Manager")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        desc = QLabel("Download regions to search, navigate, and view offline without internet.")
        desc.setWordWrap(True)
        desc.setObjectName("SubText")
        layout.addWidget(desc)

        # Download Selection Button
        self.btn_select_bbox = QPushButton("📐 Select Region on Map")
        self.btn_select_bbox.setObjectName("SecondaryBtn")
        self.btn_select_bbox.clicked.connect(self._start_bbox_selection)
        layout.addWidget(self.btn_select_bbox)

        # Preset Regions Dropdown
        preset_layout = QHBoxLayout()
        self.combo_presets = QComboBox()
        for p in PRESET_REGIONS:
            self.combo_presets.addItem(p["name"], p)
        btn_dl_preset = QPushButton("Download")
        btn_dl_preset.clicked.connect(self._download_selected_preset)
        preset_layout.addWidget(self.combo_presets, 1)
        preset_layout.addWidget(btn_dl_preset)
        layout.addLayout(preset_layout)

        # Download Progress Indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        self.progress_label.setObjectName("SubText")
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        # Downloaded Regions List
        lbl_regions = QLabel("Downloaded Regions:")
        lbl_regions.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(lbl_regions)

        self.list_downloaded = QListWidget()
        self.list_downloaded.setObjectName("DownloadedRegionsList")
        layout.addWidget(self.list_downloaded, 1)

        btn_delete_reg = QPushButton("🗑️ Delete Selected Region")
        btn_delete_reg.clicked.connect(self._delete_selected_region)
        layout.addWidget(btn_delete_reg)

        return page

    # ==========================
    # Page 4: Saved Places / Bookmarks UI
    # ==========================
    def _create_bookmarks_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Saved Places")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        self.list_bookmarks = QListWidget()
        self.list_bookmarks.setObjectName("BookmarksList")
        layout.addWidget(self.list_bookmarks, 1)

        # Bookmark action buttons
        btn_row = QHBoxLayout()
        btn_nav_bookmark = QPushButton("🧭 Navigate To")
        btn_nav_bookmark.clicked.connect(self._navigate_to_selected_bookmark)
        btn_del_bookmark = QPushButton("🗑️ Delete")
        btn_del_bookmark.clicked.connect(self._delete_selected_bookmark)
        btn_row.addWidget(btn_nav_bookmark)
        btn_row.addWidget(btn_del_bookmark)
        layout.addLayout(btn_row)

        return page

    # ==========================
    # Page 5: Settings UI
    # ==========================
    def _create_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)

        # Dark Mode Switch
        self.check_dark_mode = QCheckBox("Dark Mode Theme")
        self.check_dark_mode.setChecked(self.settings.is_dark)
        self.check_dark_mode.toggled.connect(self._on_theme_toggled)
        layout.addWidget(self.check_dark_mode)

        # Force Offline Mode Switch
        self.check_offline_mode = QCheckBox("Force Offline-Only Mode")
        self.check_offline_mode.setToolTip("Blocks all internet calls to guarantee 100% offline testing.")
        self.check_offline_mode.setChecked(self.settings.is_offline_mode)
        self.check_offline_mode.toggled.connect(self._on_offline_toggled)
        layout.addWidget(self.check_offline_mode)

        # Storage info card
        self.storage_card = QFrame()
        self.storage_card.setObjectName("StorageCard")
        sc_layout = QVBoxLayout(self.storage_card)
        self.lbl_storage_stats = QLabel("Calculating storage usage...")
        self.lbl_storage_stats.setWordWrap(True)
        sc_layout.addWidget(self.lbl_storage_stats)
        btn_clear_cache = QPushButton("Clear Temporary Cache")
        btn_clear_cache.clicked.connect(self._clear_temp_cache)
        sc_layout.addWidget(btn_clear_cache)
        layout.addWidget(self.storage_card)

        # App Info
        info = QLabel(f"{APP_NAME} v{APP_VERSION}\nBuilt with PySide6, Leaflet.js, OpenStreetMap & NetworkX.")
        info.setObjectName("SubText")
        layout.addWidget(info)

        layout.addStretch()
        return page

    # ==========================
    # Bottom Navigation HUD
    # ==========================
    def _create_nav_hud(self) -> QWidget:
        hud = QFrame()
        hud.setObjectName("NavHUD")
        hud.setFixedHeight(110)
        layout = QHBoxLayout(hud)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(20)

        # Turn maneuver icon & text
        self.lbl_hud_icon = QLabel("🧭")
        self.lbl_hud_icon.setFont(QFont("Segoe UI Emoji", 26))
        self.lbl_hud_icon.setFixedWidth(50)
        layout.addWidget(self.lbl_hud_icon)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.lbl_hud_turn = QLabel("Proceed along route")
        self.lbl_hud_turn.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.lbl_hud_sub = QLabel("Calculating...")
        self.lbl_hud_sub.setFont(QFont("Segoe UI", 12))
        self.lbl_hud_sub.setObjectName("SubText")
        text_layout.addWidget(self.lbl_hud_turn)
        text_layout.addWidget(self.lbl_hud_sub)
        layout.addLayout(text_layout, 1)

        # Stats (Distance, ETA, Speed)
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(2)
        self.lbl_hud_metrics = QLabel("0.0 km • 0 min")
        self.lbl_hud_metrics.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        self.lbl_hud_speed = QLabel("Speed: 0 km/h")
        self.lbl_hud_speed.setObjectName("SubText")
        stats_layout.addWidget(self.lbl_hud_metrics)
        stats_layout.addWidget(self.lbl_hud_speed)
        layout.addLayout(stats_layout)

        # Control Buttons
        btn_layout = QVBoxLayout()
        self.btn_hud_simulate = QPushButton("▶ Start Navigation")
        self.btn_hud_simulate.setObjectName("SuccessBtn")
        self.btn_hud_simulate.clicked.connect(self._toggle_navigation_simulation)
        self.btn_hud_close = QPushButton("✕ Exit")
        self.btn_hud_close.clicked.connect(self._clear_navigation)
        btn_layout.addWidget(self.btn_hud_simulate)
        btn_layout.addWidget(self.btn_hud_close)
        layout.addLayout(btn_layout)

        return hud

    # ==========================
    # Signal Wiring
    # ==========================
    def _wire_signals(self):
        # MapBridge signals
        self.map_view.bridge.mapClicked.connect(self._on_map_clicked)
        self.map_view.bridge.regionSelected.connect(self._on_region_selected)
        self.map_view.bridge.navigationPointSet.connect(self._on_navigation_point_set)
        self.map_view.bridge.bookmarkRequested.connect(self._on_bookmark_requested)
        self.map_view.bridge.currentLocationRequested.connect(self._on_current_location_requested)
        self.map_view.bridge.mapReady.connect(self._on_map_ready)

        # Search signals
        self.input_search.textChanged.connect(self._on_search_text_changed)
        self.search_controller.searchResultsUpdated.connect(self._on_search_results_ready)
        self.list_search_results.itemClicked.connect(self._on_search_item_clicked)

        # Nav controller signals
        self.nav_controller.routeCalculated.connect(self._on_route_calculated)
        self.nav_controller.routeCleared.connect(self._on_route_cleared)
        self.nav_controller.routeError.connect(lambda err: QMessageBox.warning(self, "Route Unavailable", err))
        self.list_nav_steps.itemClicked.connect(self._on_step_item_clicked)

        # GPS signals
        self.gps_sim.locationUpdated.connect(self._on_gps_location_updated)
        self.gps_sim.stepProgress.connect(self._on_gps_step_progress)
        self.gps_sim.destinationReached.connect(self._on_gps_destination_reached)

        # Bookmark list clicks
        self.list_bookmarks.itemClicked.connect(self._on_bookmark_item_clicked)
        self.list_downloaded.itemClicked.connect(self._on_region_item_clicked)

    def _initial_sync(self):
        self._refresh_downloaded_regions_list()
        self._refresh_bookmarks_list()
        self._update_storage_stats()

    # ==========================
    # Map & Navigation Handlers
    # ==========================
    def _on_map_ready(self):
        self.map_view.set_theme(self.settings.is_dark)
        self.map_view.set_offline_status(self.settings.is_offline_mode)
        regions = self.db.get_all_regions()
        self.map_view.highlight_regions(regions)

    def _on_map_clicked(self, lat: float, lng: float):
        logger.debug(f"Map clicked at: {lat}, {lng}")

    def _on_navigation_point_set(self, point_type: str, lat: float, lng: float, name: str):
        self.sidebar_stack.setCurrentIndex(1)
        self.btn_tab_nav.setChecked(True)

        if point_type == "start":
            self.nav_controller.set_start(lat, lng, name)
            self.input_start.setText(f"{name} ({round(lat, 3)}, {round(lng, 3)})")
        else:
            self.nav_controller.set_destination(lat, lng, name)
            self.input_dest.setText(f"{name} ({round(lat, 3)}, {round(lng, 3)})")

        if self.nav_controller.start_point and self.nav_controller.dest_point:
            self.nav_controller.calculate_route()

    def _on_calculate_route(self):
        self.nav_controller.calculate_route()

    def _swap_nav_endpoints(self):
        self.nav_controller.swap_endpoints()
        s = self.input_start.text()
        self.input_start.setText(self.input_dest.text())
        self.input_dest.setText(s)
        if self.nav_controller.start_point and self.nav_controller.dest_point:
            self.nav_controller.calculate_route()

    def _clear_navigation(self):
        self.gps_sim.stop_simulation()
        self.nav_controller.clear()
        self.input_start.clear()
        self.input_dest.clear()
        self.list_nav_steps.clear()
        self.map_view.clear_route()
        self.nav_hud.setVisible(False)
        self.btn_hud_simulate.setText("▶ Start Navigation")

    def _on_route_calculated(self, route_data: dict):
        prim = route_data.get("primary_route", {})
        alt = route_data.get("alternative_route") or {}
        coords = prim.get("coordinates", [])
        alt_coords = alt.get("coordinates", [])
        steps = prim.get("turn_steps", [])

        # Display on Leaflet map
        self.map_view.display_route(coords, alt_coords, steps)

        # Populate sidebar steps list
        self.list_nav_steps.clear()
        for s in steps:
            icon = "🏁" if s["type"] == "arrive" else "➜"
            text = f"{icon} {s['instruction']} ({s.get('distance_text', '')})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.list_nav_steps.addItem(item)

        # Show bottom HUD
        self.nav_hud.setVisible(True)
        if steps:
            self.lbl_hud_turn.setText(steps[0]["instruction"])
            self.lbl_hud_sub.setText(f"Next turn in {steps[0].get('distance_text', '')}")
        self.lbl_hud_metrics.setText(f"{prim.get('distance_text', '')} • {prim.get('duration_text', '')}")
        self.lbl_hud_speed.setText("Speed: 0 km/h")
        self.btn_hud_simulate.setText("▶ Start Navigation")

    def _on_route_cleared(self):
        self.map_view.clear_route()
        self.nav_hud.setVisible(False)

    def _on_step_item_clicked(self, item: QListWidgetItem):
        step = item.data(Qt.ItemDataRole.UserRole)
        if step and "lat" in step and "lng" in step:
            self.map_view.fly_to(step["lat"], step["lng"], 17)

    def _toggle_navigation_simulation(self):
        if self.gps_sim.is_simulating:
            self.gps_sim.stop_simulation()
            self.btn_hud_simulate.setText("▶ Resume Navigation")
        else:
            if not self.nav_controller.current_route_data:
                return
            prim = self.nav_controller.current_route_data.get("primary_route", {})
            coords = prim.get("coordinates", [])
            steps = prim.get("turn_steps", [])
            self.gps_sim.start_navigation_simulation(coords, steps, speed_multiplier=2.5)
            self.btn_hud_simulate.setText("⏸ Pause Navigation")

    def _on_gps_location_updated(self, lat: float, lng: float, heading: float, speed_kmh: float, accuracy: float):
        self.map_view.update_gps(lat, lng, heading, accuracy)
        self.lbl_hud_speed.setText(f"Speed: {speed_kmh} km/h")

    def _on_gps_step_progress(self, step_index: int, distance_to_next_m: float):
        if self.nav_controller.current_route_data:
            steps = self.nav_controller.current_route_data.get("primary_route", {}).get("turn_steps", [])
            if step_index < len(steps):
                s = steps[step_index]
                self.lbl_hud_turn.setText(s["instruction"])
                dist_txt = f"{int(round(distance_to_next_m))} m" if distance_to_next_m < 1000 else f"{round(distance_to_next_m/1000, 1)} km"
                self.lbl_hud_sub.setText(f"In {dist_txt}")

    def _on_gps_destination_reached(self):
        self.lbl_hud_turn.setText("You have arrived at your destination!")
        self.lbl_hud_sub.setText("Offline Navigation Completed")
        self.btn_hud_simulate.setText("▶ Completed")
        QMessageBox.information(self, "Navigation Complete", "You have arrived at your destination!")

    def _on_current_location_requested(self):
        lat, lng = self.gps_sim.current_lat, self.gps_sim.current_lng
        self.map_view.fly_to(lat, lng, 16)
        self.map_view.update_gps(lat, lng)

    # ==========================
    # Search Handlers
    # ==========================
    def _on_search_text_changed(self, text: str):
        self.search_controller.execute_search(text)

    def _on_chip_clicked(self, category: str):
        if category == "All":
            self.input_search.setText("Street")
        else:
            self.input_search.setText(category)

    def _on_search_results_ready(self, results: list):
        self.list_search_results.clear()
        for res in results:
            title = res["name"]
            cat = res.get("category", "")
            city = res.get("city", "")
            sub = f"{cat} • {city}" if city else cat
            item = QListWidgetItem(f"📍 {title}\n    {sub}")
            item.setData(Qt.ItemDataRole.UserRole, res)
            self.list_search_results.addItem(item)

    def _on_search_item_clicked(self, item: QListWidgetItem):
        res = item.data(Qt.ItemDataRole.UserRole)
        if res:
            lat = res["lat"]
            lng = res["lng"]
            name = res["name"]
            sub = res.get("street") or res.get("category", "")
            self.map_view.show_location_pin(lat, lng, name, sub)

    # ==========================
    # Downloads & Regions
    # ==========================
    def _start_bbox_selection(self):
        self.map_view.start_region_selection()

    def _on_region_selected(self, min_lat: float, min_lng: float, max_lat: float, max_lng: float):
        self.sidebar_stack.setCurrentIndex(2)
        self.btn_tab_downloads.setChecked(True)

        name, ok = QInputDialog.getText(
            self, "Download Map Region", "Enter a name for this offline region:",
            text=f"Custom Region ({round(min_lat, 2)}, {round(min_lng, 2)})"
        )
        if ok and name.strip():
            region_id = f"reg_{int(min_lat*100)}_{int(min_lng*100)}"
            self._start_download_worker(region_id, name.strip(), min_lat, min_lng, max_lat, max_lng)

    def _download_selected_preset(self):
        preset = self.combo_presets.currentData()
        if not preset:
            return
        self._start_download_worker(
            region_id=preset["id"],
            name=preset["name"],
            min_lat=preset["min_lat"],
            min_lng=preset["min_lng"],
            max_lat=preset["max_lat"],
            max_lng=preset["max_lng"],
            zoom_levels=preset.get("zoom_levels", [12, 13, 14, 15])
        )

    def _start_download_worker(self, region_id: str, name: str, min_lat: float, min_lng: float, max_lat: float, max_lng: float, zoom_levels=None):
        if self.active_download_worker and self.active_download_worker.isRunning():
            QMessageBox.warning(self, "Download in Progress", "Please wait for current download to finish.")
            return

        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Preparing download for '{name}'...")

        self.active_download_worker = DownloadWorker(
            db=self.db,
            region_id=region_id,
            name=name,
            min_lat=min_lat,
            min_lng=min_lng,
            max_lat=max_lat,
            max_lng=max_lng,
            zoom_levels=zoom_levels
        )
        self.active_download_worker.progress.connect(self._on_download_progress)
        self.active_download_worker.finishedRegion.connect(self._on_download_finished)
        self.active_download_worker.error.connect(self._on_download_error)
        self.active_download_worker.start()

    def _on_download_progress(self, current: int, total: int, message: str):
        pct = int((current / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.progress_label.setText(message)

    def _on_download_finished(self, region: Region):
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        QMessageBox.information(
            self, "Download Complete",
            f"Region '{region.name}' downloaded successfully!\n"
            f"Tiles: {region.tile_count}\n"
            f"Size: {region.size_mb} MB\n"
            f"Offline routing data: {'Ready' if region.has_routing else 'Basic'}"
        )
        self._refresh_downloaded_regions_list()
        self._update_storage_stats()
        # Reload road network
        self.route_engine.reload_network()

    def _on_download_error(self, err_msg: str):
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        QMessageBox.warning(self, "Download Issue", err_msg)
        self._refresh_downloaded_regions_list()

    def _refresh_downloaded_regions_list(self):
        self.list_downloaded.clear()
        regions = self.db.get_all_regions()
        for r in regions:
            item = QListWidgetItem(f"🗺️ {r.name}\n    {r.tile_count} tiles • {r.size_mb} MB • Status: {r.status}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.list_downloaded.addItem(item)
        self.map_view.highlight_regions(regions)

    def _on_region_item_clicked(self, item: QListWidgetItem):
        region: Region = item.data(Qt.ItemDataRole.UserRole)
        if region:
            self.map_view.fit_bounds(region.min_lat, region.min_lng, region.max_lat, region.max_lng)

    def _delete_selected_region(self):
        item = self.list_downloaded.currentItem()
        if not item:
            QMessageBox.information(self, "Select Region", "Please click on a region to delete.")
            return
        region: Region = item.data(Qt.ItemDataRole.UserRole)
        confirm = QMessageBox.question(
            self, "Delete Region",
            f"Are you sure you want to delete '{region.name}' and all its offline map data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.delete_region(region.id)
            self._refresh_downloaded_regions_list()
            self._update_storage_stats()
            self.route_engine.reload_network()

    # ==========================
    # Bookmarks
    # ==========================
    def _on_bookmark_requested(self, lat: float, lng: float, default_name: str):
        name, ok = QInputDialog.getText(self, "Save Bookmark", "Enter name for this place:", text=default_name)
        if ok and name.strip():
            bm = Bookmark(id=None, name=name.strip(), category="Favorite", lat=lat, lng=lng, address=f"{round(lat, 4)}, {round(lng, 4)}")
            self.db.add_bookmark(bm)
            self._refresh_bookmarks_list()
            self.sidebar_stack.setCurrentIndex(3)
            self.btn_tab_bookmarks.setChecked(True)
            QMessageBox.information(self, "Bookmark Saved", f"'{name}' saved to your places.")

    def _refresh_bookmarks_list(self):
        self.list_bookmarks.clear()
        bookmarks = self.db.get_bookmarks()
        for b in bookmarks:
            item = QListWidgetItem(f"⭐ {b.name}\n    {b.category} • {b.address}")
            item.setData(Qt.ItemDataRole.UserRole, b)
            self.list_bookmarks.addItem(item)

    def _on_bookmark_item_clicked(self, item: QListWidgetItem):
        bm: Bookmark = item.data(Qt.ItemDataRole.UserRole)
        if bm:
            self.map_view.show_location_pin(bm.lat, bm.lng, bm.name, bm.address)

    def _navigate_to_selected_bookmark(self):
        item = self.list_bookmarks.currentItem()
        if not item:
            return
        bm: Bookmark = item.data(Qt.ItemDataRole.UserRole)
        if bm:
            self._on_navigation_point_set("dest", bm.lat, bm.lng, bm.name)

    def _delete_selected_bookmark(self):
        item = self.list_bookmarks.currentItem()
        if not item:
            return
        bm: Bookmark = item.data(Qt.ItemDataRole.UserRole)
        if bm and bm.id:
            self.db.delete_bookmark(bm.id)
            self._refresh_bookmarks_list()

    # ==========================
    # Settings & Theme
    # ==========================
    def _on_theme_toggled(self, is_dark: bool):
        self.settings.set_dark_mode(is_dark)
        self.map_view.set_theme(is_dark)
        self._apply_theme(is_dark)

    def _on_offline_toggled(self, is_offline: bool):
        self.settings.set_offline_mode(is_offline)
        self.tile_server.set_offline_mode(is_offline)
        self.search_controller.set_offline_mode(is_offline)
        self.map_view.set_offline_status(is_offline)

    def _update_storage_stats(self):
        stats = self.db.get_storage_stats()
        text = (
            f"<b>Storage Overview:</b><br>"
            f"• Downloaded Regions: {stats['region_count']}<br>"
            f"• Cached Map Tiles: {stats['tile_count']} tiles<br>"
            f"• Disk Usage: {stats['tile_size_mb']} MB<br>"
            f"• Offline POIs: {stats['poi_count']}<br>"
            f"• Saved Bookmarks: {stats['bookmark_count']}"
        )
        self.lbl_storage_stats.setText(text)

    def _clear_temp_cache(self):
        res = self.settings.clear_tile_cache()
        self._update_storage_stats()
        QMessageBox.information(
            self, "Cache Cleared",
            f"Cleared temporary cached tiles.\nFreed: {res['freed_mb']} MB\nRemaining (Downloaded Regions): {res['remaining_mb']} MB"
        )

    def _apply_theme(self, is_dark: bool):
        if is_dark:
            # Modern Dark Theme QSS
            self.setStyleSheet("""
                QMainWindow, QWidget#NavRail, QWidget#SidebarPanel {
                    background-color: #121824;
                    color: #f1f5f9;
                }
                QWidget#NavRail {
                    background-color: #0d121c;
                    border-right: 1px solid #1e293b;
                }
                QPushButton[id^="RailBtn_"] {
                    background-color: transparent;
                    border: none;
                    border-radius: 8px;
                    color: #94a3b8;
                }
                QPushButton[id^="RailBtn_"]:hover {
                    background-color: #1e293b;
                    color: #f8fafc;
                }
                QPushButton[id^="RailBtn_"]:checked {
                    background-color: #2563eb;
                    color: #ffffff;
                }
                QWidget#SidebarPanel {
                    border-right: 1px solid #1e293b;
                }
                QLineEdit {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 8px 12px;
                    color: #f8fafc;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border: 1px solid #3b82f6;
                }
                QListWidget {
                    background-color: #1a2232;
                    border: 1px solid #283548;
                    border-radius: 8px;
                    padding: 4px;
                    color: #f1f5f9;
                }
                QListWidget::item {
                    border-radius: 6px;
                    padding: 8px;
                    margin-bottom: 4px;
                }
                QListWidget::item:hover {
                    background-color: #243046;
                }
                QListWidget::item:selected {
                    background-color: #1e3a8a;
                    color: #93c5fd;
                }
                QPushButton#PrimaryBtn {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 10px;
                    font-weight: bold;
                }
                QPushButton#PrimaryBtn:hover {
                    background-color: #1d4ed8;
                }
                QPushButton#SecondaryBtn {
                    background-color: #1e293b;
                    color: #f1f5f9;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 8px;
                }
                QPushButton#ChipBtn {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 12px;
                    padding: 4px 10px;
                    font-size: 11px;
                    color: #94a3b8;
                }
                QPushButton#ChipBtn:hover {
                    border-color: #3b82f6;
                    color: #f8fafc;
                }
                QFrame#EndpointsCard, QFrame#StorageCard {
                    background-color: #1a2232;
                    border: 1px solid #283548;
                    border-radius: 8px;
                }
                QLabel#EndpointBadgeA {
                    background-color: #10b981;
                    color: #ffffff;
                    border-radius: 10px;
                    padding: 2px 8px;
                    font-weight: bold;
                }
                QLabel#EndpointBadgeB {
                    background-color: #ef4444;
                    color: #ffffff;
                    border-radius: 10px;
                    padding: 2px 8px;
                    font-weight: bold;
                }
                QFrame#NavHUD {
                    background-color: #121824;
                    border-top: 1px solid #1e293b;
                }
                QPushButton#SuccessBtn {
                    background-color: #10b981;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 14px;
                    font-weight: bold;
                }
                QPushButton#SuccessBtn:hover {
                    background-color: #059669;
                }
                QLabel#SubText {
                    color: #94a3b8;
                    font-size: 12px;
                }
            """)
        else:
            # Modern Light Theme QSS (Google Maps aesthetic)
            self.setStyleSheet("""
                QMainWindow, QWidget#NavRail, QWidget#SidebarPanel {
                    background-color: #ffffff;
                    color: #1f2937;
                }
                QWidget#NavRail {
                    background-color: #f8fafc;
                    border-right: 1px solid #e2e8f0;
                }
                QPushButton[id^="RailBtn_"] {
                    background-color: transparent;
                    border: none;
                    border-radius: 8px;
                    color: #64748b;
                }
                QPushButton[id^="RailBtn_"]:hover {
                    background-color: #e2e8f0;
                    color: #0f172a;
                }
                QPushButton[id^="RailBtn_"]:checked {
                    background-color: #2563eb;
                    color: #ffffff;
                }
                QWidget#SidebarPanel {
                    border-right: 1px solid #e2e8f0;
                }
                QLineEdit {
                    background-color: #f1f5f9;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    padding: 8px 12px;
                    color: #0f172a;
                    font-size: 13px;
                }
                QLineEdit:focus {
                    border: 1px solid #2563eb;
                    background-color: #ffffff;
                }
                QListWidget {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    padding: 4px;
                    color: #1f2937;
                }
                QListWidget::item {
                    border-radius: 6px;
                    padding: 8px;
                    margin-bottom: 4px;
                }
                QListWidget::item:hover {
                    background-color: #f1f5f9;
                }
                QListWidget::item:selected {
                    background-color: #dbeafe;
                    color: #1e40af;
                }
                QPushButton#PrimaryBtn {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 10px;
                    font-weight: bold;
                }
                QPushButton#PrimaryBtn:hover {
                    background-color: #1d4ed8;
                }
                QPushButton#SecondaryBtn {
                    background-color: #ffffff;
                    color: #1f2937;
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    padding: 8px;
                }
                QPushButton#ChipBtn {
                    background-color: #f1f5f9;
                    border: 1px solid #e2e8f0;
                    border-radius: 12px;
                    padding: 4px 10px;
                    font-size: 11px;
                    color: #475569;
                }
                QPushButton#ChipBtn:hover {
                    border-color: #2563eb;
                    color: #1e40af;
                }
                QFrame#EndpointsCard, QFrame#StorageCard {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                }
                QLabel#EndpointBadgeA {
                    background-color: #10b981;
                    color: #ffffff;
                    border-radius: 10px;
                    padding: 2px 8px;
                    font-weight: bold;
                }
                QLabel#EndpointBadgeB {
                    background-color: #ef4444;
                    color: #ffffff;
                    border-radius: 10px;
                    padding: 2px 8px;
                    font-weight: bold;
                }
                QFrame#NavHUD {
                    background-color: #ffffff;
                    border-top: 1px solid #e2e8f0;
                }
                QPushButton#SuccessBtn {
                    background-color: #10b981;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 14px;
                    font-weight: bold;
                }
                QPushButton#SuccessBtn:hover {
                    background-color: #059669;
                }
                QLabel#SubText {
                    color: #64748b;
                    font-size: 12px;
                }
            """)
