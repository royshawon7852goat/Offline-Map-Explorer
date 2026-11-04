"""Application Settings Manager for OfflineMap Explorer
Handles persistent configuration in SQLite for dark mode, offline mode,
routing profiles, and storage maintenance.
"""

from typing import Any, Dict
from PySide6.QtCore import QObject, Signal
from database.database import Database

class SettingsManager(QObject):
    themeChanged = Signal(bool)        # is_dark
    offlineModeChanged = Signal(bool)  # is_offline
    layerChanged = Signal(str)         # layer_id

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._load_defaults()

    def _load_defaults(self):
        if self.db.get_setting("is_dark") is None:
            self.db.set_setting("is_dark", False)
        if self.db.get_setting("is_offline_mode") is None:
            self.db.set_setting("is_offline_mode", False)
        if self.db.get_setting("active_layer") is None:
            self.db.set_setting("active_layer", "standard")

    @property
    def is_dark(self) -> bool:
        return bool(self.db.get_setting("is_dark", False))

    def set_dark_mode(self, is_dark: bool):
        self.db.set_setting("is_dark", is_dark)
        self.themeChanged.emit(is_dark)

    @property
    def is_offline_mode(self) -> bool:
        return bool(self.db.get_setting("is_offline_mode", False))

    def set_offline_mode(self, is_offline: bool):
        self.db.set_setting("is_offline_mode", is_offline)
        self.offlineModeChanged.emit(is_offline)

    @property
    def active_layer(self) -> str:
        return str(self.db.get_setting("active_layer", "standard"))

    def set_active_layer(self, layer_id: str):
        self.db.set_setting("active_layer", layer_id)
        self.layerChanged.emit(layer_id)

    def clear_tile_cache(self) -> Dict[str, Any]:
        """Clears cached tiles while retaining region metadata."""
        stats_before = self.db.get_storage_stats()
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM tiles WHERE region_id IS NULL OR region_id = '';")
        stats_after = self.db.get_storage_stats()
        freed_mb = round(stats_before["tile_size_mb"] - stats_after["tile_size_mb"], 2)
        return {
            "freed_mb": max(0.0, freed_mb),
            "remaining_mb": stats_after["tile_size_mb"]
        }
