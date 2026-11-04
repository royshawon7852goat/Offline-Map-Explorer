"""SQLite Database Manager for OfflineMap Explorer
Handles persistent tile caching, downloaded region metadata, POIs with FTS5 search,
bookmarks, navigation history, and road network routing data.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from config import DB_PATH
from database.models import Region, Bookmark, NavigationHistoryItem, POI

logger = logging.getLogger("OfflineMap.Database")

class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high performance concurrent reads and writes
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            # Tiles table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tiles (
                    z INTEGER,
                    x INTEGER,
                    y INTEGER,
                    data BLOB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    region_id TEXT,
                    PRIMARY KEY (z, x, y)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tiles_region ON tiles (region_id);")

            # Regions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS regions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    min_lat REAL NOT NULL,
                    min_lng REAL NOT NULL,
                    max_lat REAL NOT NULL,
                    max_lng REAL NOT NULL,
                    min_zoom INTEGER NOT NULL,
                    max_zoom INTEGER NOT NULL,
                    tile_count INTEGER DEFAULT 0,
                    size_bytes INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'completed',
                    has_routing INTEGER DEFAULT 0
                );
            """)

            # Points of interest table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pois (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    street TEXT DEFAULT '',
                    city TEXT DEFAULT '',
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    region_id TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pois_region ON pois (region_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pois_coords ON pois (lat, lng);")

            # Full-Text Search 5 for instant offline search suggestions
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS pois_fts USING fts5(
                    name,
                    category,
                    street,
                    city,
                    content='pois',
                    content_rowid='id'
                );
            """)

            # Triggers to keep FTS5 in sync with pois table
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS pois_ai AFTER INSERT ON pois BEGIN
                    INSERT INTO pois_fts(rowid, name, category, street, city)
                    VALUES (new.id, new.name, new.category, new.street, new.city);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS pois_ad AFTER DELETE ON pois BEGIN
                    INSERT INTO pois_fts(pois_fts, rowid, name, category, street, city)
                    VALUES('delete', old.id, old.name, old.category, old.street, old.city);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS pois_au AFTER UPDATE ON pois BEGIN
                    INSERT INTO pois_fts(pois_fts, rowid, name, category, street, city)
                    VALUES('delete', old.id, old.name, old.category, old.street, old.city);
                    INSERT INTO pois_fts(rowid, name, category, street, city)
                    VALUES (new.id, new.name, new.category, new.street, new.city);
                END;
            """)

            # Bookmarks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT DEFAULT 'Favorite',
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    address TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Navigation history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS navigation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_name TEXT NOT NULL,
                    start_lat REAL NOT NULL,
                    start_lng REAL NOT NULL,
                    dest_name TEXT NOT NULL,
                    dest_lat REAL NOT NULL,
                    dest_lng REAL NOT NULL,
                    mode TEXT DEFAULT 'driving',
                    distance_km REAL NOT NULL,
                    duration_min REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Settings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)

            # Road Network Routing tables for downloaded regions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS road_nodes (
                    id INTEGER,
                    lat REAL NOT NULL,
                    lng REAL NOT NULL,
                    region_id TEXT NOT NULL,
                    PRIMARY KEY (region_id, id)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_road_nodes_region ON road_nodes(region_id);")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS road_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    u INTEGER NOT NULL,
                    v INTEGER NOT NULL,
                    length_m REAL NOT NULL,
                    speed_kmh REAL NOT NULL,
                    road_type TEXT NOT NULL,
                    oneway INTEGER DEFAULT 0,
                    name TEXT DEFAULT '',
                    region_id TEXT NOT NULL,
                    geometry_json TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_road_edges_region ON road_edges(region_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_road_edges_uv ON road_edges(region_id, u, v);")

    # ==========================
    # Tile Operations
    # ==========================
    def save_tile(self, z: int, x: int, y: int, data: bytes, region_id: Optional[str] = None) -> bool:
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO tiles (z, x, y, data, updated_at, region_id)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?);
                """, (z, x, y, data, region_id))
            return True
        except Exception as e:
            logger.error(f"Error saving tile {z}/{x}/{y}: {e}")
            return False

    def save_tiles_batch(self, tiles: List[Tuple[int, int, int, bytes, Optional[str]]]) -> int:
        if not tiles:
            return 0
        try:
            with self.get_connection() as conn:
                conn.executemany("""
                    INSERT OR REPLACE INTO tiles (z, x, y, data, updated_at, region_id)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?);
                """, tiles)
            return len(tiles)
        except Exception as e:
            logger.error(f"Error saving batch of tiles: {e}")
            return 0

    def get_tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        try:
            with self.get_connection() as conn:
                cur = conn.execute("SELECT data FROM tiles WHERE z = ? AND x = ? AND y = ?;", (z, x, y))
                row = cur.fetchone()
                return row["data"] if row else None
        except Exception as e:
            logger.error(f"Error getting tile {z}/{x}/{y}: {e}")
            return None

    def delete_region_tiles(self, region_id: str) -> int:
        try:
            with self.get_connection() as conn:
                cur = conn.execute("DELETE FROM tiles WHERE region_id = ?;", (region_id,))
                return cur.rowcount
        except Exception as e:
            logger.error(f"Error deleting tiles for region {region_id}: {e}")
            return 0

    def get_storage_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT COUNT(*), TOTAL(LENGTH(data)) FROM tiles;")
            tile_count, tile_bytes = cur.fetchone()
            cur = conn.execute("SELECT COUNT(*) FROM regions;")
            region_count = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM bookmarks;")
            bookmark_count = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM pois;")
            poi_count = cur.fetchone()[0]
        return {
            "tile_count": int(tile_count or 0),
            "tile_size_mb": round((tile_bytes or 0) / (1024 * 1024), 2),
            "region_count": int(region_count or 0),
            "bookmark_count": int(bookmark_count or 0),
            "poi_count": int(poi_count or 0),
        }

    # ==========================
    # Region Operations
    # ==========================
    def add_region(self, region: Region) -> bool:
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO regions (
                        id, name, min_lat, min_lng, max_lat, max_lng,
                        min_zoom, max_zoom, tile_count, size_bytes,
                        status, has_routing, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, (
                    region.id, region.name, region.min_lat, region.min_lng,
                    region.max_lat, region.max_lng, region.min_zoom, region.max_zoom,
                    region.tile_count, region.size_bytes, region.status,
                    1 if region.has_routing else 0
                ))
            return True
        except Exception as e:
            logger.error(f"Error adding region {region.id}: {e}")
            return False

    def update_region_status(self, region_id: str, status: str, tile_count: int, size_bytes: int, has_routing: bool = False):
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE regions
                SET status = ?, tile_count = ?, size_bytes = ?, has_routing = ?
                WHERE id = ?;
            """, (status, tile_count, size_bytes, 1 if has_routing else 0, region_id))

    def get_region(self, region_id: str) -> Optional[Region]:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM regions WHERE id = ?;", (region_id,))
            row = cur.fetchone()
            if row:
                return Region(
                    id=row["id"],
                    name=row["name"],
                    min_lat=row["min_lat"],
                    min_lng=row["min_lng"],
                    max_lat=row["max_lat"],
                    max_lng=row["max_lng"],
                    min_zoom=row["min_zoom"],
                    max_zoom=row["max_zoom"],
                    tile_count=row["tile_count"],
                    size_bytes=row["size_bytes"],
                    created_at=str(row["created_at"]),
                    status=row["status"],
                    has_routing=bool(row["has_routing"])
                )
        return None

    def get_all_regions(self) -> List[Region]:
        regions = []
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM regions ORDER BY created_at DESC;")
            for row in cur.fetchall():
                regions.append(Region(
                    id=row["id"],
                    name=row["name"],
                    min_lat=row["min_lat"],
                    min_lng=row["min_lng"],
                    max_lat=row["max_lat"],
                    max_lng=row["max_lng"],
                    min_zoom=row["min_zoom"],
                    max_zoom=row["max_zoom"],
                    tile_count=row["tile_count"],
                    size_bytes=row["size_bytes"],
                    created_at=str(row["created_at"]),
                    status=row["status"],
                    has_routing=bool(row["has_routing"])
                ))
        return regions

    def delete_region(self, region_id: str) -> bool:
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM regions WHERE id = ?;", (region_id,))
                conn.execute("DELETE FROM tiles WHERE region_id = ?;", (region_id,))
                conn.execute("DELETE FROM pois WHERE region_id = ?;", (region_id,))
                conn.execute("DELETE FROM road_nodes WHERE region_id = ?;", (region_id,))
                conn.execute("DELETE FROM road_edges WHERE region_id = ?;", (region_id,))
            return True
        except Exception as e:
            logger.error(f"Error deleting region {region_id}: {e}")
            return False

    # ==========================
    # POI / Search Operations
    # ==========================
    def insert_pois_batch(self, pois: List[POI]) -> int:
        if not pois:
            return 0
        try:
            data = [(p.name, p.category, p.street, p.city, p.lat, p.lng, p.region_id) for p in pois]
            with self.get_connection() as conn:
                conn.executemany("""
                    INSERT INTO pois (name, category, street, city, lat, lng, region_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, data)
            return len(pois)
        except Exception as e:
            logger.error(f"Error inserting POIs batch: {e}")
            return 0

    def search_pois(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        
        # Clean query for FTS5 syntax
        clean_q = "".join([c if c.isalnum() or c.isspace() else " " for c in query]).strip()
        if not clean_q:
            return []

        fts_query = " ".join([f'"{token}"*' for token in clean_q.split()])
        results = []

        try:
            with self.get_connection() as conn:
                cur = conn.execute("""
                    SELECT p.id, p.name, p.category, p.street, p.city, p.lat, p.lng, p.region_id,
                           rank
                    FROM pois_fts f
                    JOIN pois p ON f.rowid = p.id
                    WHERE pois_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?;
                """, (fts_query, limit))
                
                for row in cur.fetchall():
                    results.append(dict(row))
        except Exception as e:
            logger.warning(f"FTS search failed, falling back to LIKE: {e}")
            # Fallback to standard LIKE search
            like_pattern = f"%{query}%"
            with self.get_connection() as conn:
                cur = conn.execute("""
                    SELECT id, name, category, street, city, lat, lng, region_id
                    FROM pois
                    WHERE name LIKE ? OR street LIKE ? OR city LIKE ?
                    LIMIT ?;
                """, (like_pattern, like_pattern, like_pattern, limit))
                for row in cur.fetchall():
                    results.append(dict(row))

        return results

    # ==========================
    # Bookmarks Operations
    # ==========================
    def get_bookmarks(self) -> List[Bookmark]:
        bookmarks = []
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM bookmarks ORDER BY id DESC;")
            for row in cur.fetchall():
                bookmarks.append(Bookmark(
                    id=row["id"],
                    name=row["name"],
                    category=row["category"],
                    lat=row["lat"],
                    lng=row["lng"],
                    address=row["address"],
                    created_at=str(row["created_at"])
                ))
        return bookmarks

    def add_bookmark(self, bookmark: Bookmark) -> int:
        with self.get_connection() as conn:
            cur = conn.execute("""
                INSERT INTO bookmarks (name, category, lat, lng, address)
                VALUES (?, ?, ?, ?, ?);
            """, (bookmark.name, bookmark.category, bookmark.lat, bookmark.lng, bookmark.address))
            return cur.lastrowid

    def update_bookmark(self, bookmark_id: int, name: str, category: str) -> bool:
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE bookmarks SET name = ?, category = ? WHERE id = ?;
            """, (name, category, bookmark_id))
            return True

    def delete_bookmark(self, bookmark_id: int) -> bool:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM bookmarks WHERE id = ?;", (bookmark_id,))
            return True

    # ==========================
    # Navigation History Operations
    # ==========================
    def add_history(self, item: NavigationHistoryItem) -> int:
        with self.get_connection() as conn:
            cur = conn.execute("""
                INSERT INTO navigation_history (
                    start_name, start_lat, start_lng,
                    dest_name, dest_lat, dest_lng,
                    mode, distance_km, duration_min
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                item.start_name, item.start_lat, item.start_lng,
                item.dest_name, item.dest_lat, item.dest_lng,
                item.mode, item.distance_km, item.duration_min
            ))
            return cur.lastrowid

    def get_history(self, limit: int = 50) -> List[NavigationHistoryItem]:
        items = []
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM navigation_history ORDER BY id DESC LIMIT ?;", (limit,))
            for row in cur.fetchall():
                items.append(NavigationHistoryItem(
                    id=row["id"],
                    start_name=row["start_name"],
                    start_lat=row["start_lat"],
                    start_lng=row["start_lng"],
                    dest_name=row["dest_name"],
                    dest_lat=row["dest_lat"],
                    dest_lng=row["dest_lng"],
                    mode=row["mode"],
                    distance_km=row["distance_km"],
                    duration_min=row["duration_min"],
                    created_at=str(row["created_at"])
                ))
        return items

    def clear_history(self):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM navigation_history;")

    # ==========================
    # Settings Operations
    # ==========================
    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.get_connection() as conn:
            cur = conn.execute("SELECT value FROM settings WHERE key = ?;", (key,))
            row = cur.fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except Exception:
                    return row["value"]
        return default

    def set_setting(self, key: str, value: Any):
        val_str = json.dumps(value)
        with self.get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?);", (key, val_str))

    # ==========================
    # Road Network Routing Data
    # ==========================
    def save_road_network(self, region_id: str, nodes: List[Tuple[int, float, float]], edges: List[Dict[str, Any]]) -> bool:
        try:
            with self.get_connection() as conn:
                # Insert nodes
                node_data = [(n[0], n[1], n[2], region_id) for n in nodes]
                conn.executemany("""
                    INSERT OR REPLACE INTO road_nodes (id, lat, lng, region_id)
                    VALUES (?, ?, ?, ?);
                """, node_data)

                # Insert edges
                edge_data = [
                    (
                        e["u"], e["v"], e["length_m"], e["speed_kmh"],
                        e["road_type"], 1 if e.get("oneway", False) else 0,
                        e.get("name", ""), region_id, json.dumps(e.get("geometry", []))
                    )
                    for e in edges
                ]
                conn.executemany("""
                    INSERT INTO road_edges (u, v, length_m, speed_kmh, road_type, oneway, name, region_id, geometry_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, edge_data)
            return True
        except Exception as e:
            logger.error(f"Error saving road network for region {region_id}: {e}")
            return False

    def load_road_network(self, region_id: Optional[str] = None) -> Tuple[Dict[int, Tuple[float, float]], List[Dict[str, Any]]]:
        nodes: Dict[int, Tuple[float, float]] = {}
        edges: List[Dict[str, Any]] = []
        with self.get_connection() as conn:
            if region_id:
                cur_nodes = conn.execute("SELECT id, lat, lng FROM road_nodes WHERE region_id = ?;", (region_id,))
                cur_edges = conn.execute("SELECT * FROM road_edges WHERE region_id = ?;", (region_id,))
            else:
                cur_nodes = conn.execute("SELECT id, lat, lng FROM road_nodes;")
                cur_edges = conn.execute("SELECT * FROM road_edges;")

            for row in cur_nodes.fetchall():
                nodes[row["id"]] = (row["lat"], row["lng"])

            for row in cur_edges.fetchall():
                geom = []
                if row["geometry_json"]:
                    try:
                        geom = json.loads(row["geometry_json"])
                    except Exception:
                        pass
                edges.append({
                    "u": row["u"],
                    "v": row["v"],
                    "length_m": row["length_m"],
                    "speed_kmh": row["speed_kmh"],
                    "road_type": row["road_type"],
                    "oneway": bool(row["oneway"]),
                    "name": row["name"],
                    "geometry": geom,
                    "region_id": row["region_id"]
                })

        return nodes, edges
