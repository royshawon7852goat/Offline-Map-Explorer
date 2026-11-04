"""Local HTTP Tile and Asset Server for OfflineMap Explorer
Serves bundled web assets and intercepts tile requests to provide
100% offline local caching via SQLite.
"""

import http.server
import socketserver
import threading
import urllib.parse
import urllib.request
import logging
from pathlib import Path
from typing import Optional
from io import BytesIO
from PIL import Image, ImageDraw

from config import (
    FRONTEND_DIR,
    SERVER_HOST,
    SERVER_DEFAULT_PORT,
    OSM_TILE_SERVERS,
    CARTO_DARK_SERVER,
    CARTO_LIGHT_SERVER,
    USER_AGENT
)
from database.database import Database

logger = logging.getLogger("OfflineMap.TileServer")

# Pre-generate a 256x256 subtle offline placeholder tile
def create_offline_tile() -> bytes:
    img = Image.new("RGBA", (256, 256), (240, 242, 245, 255))
    draw = ImageDraw.Draw(img)
    # Subtle grid lines
    draw.line([(0, 0), (255, 0)], fill=(225, 228, 232), width=1)
    draw.line([(0, 0), (0, 255)], fill=(225, 228, 232), width=1)
    draw.line([(0, 255), (255, 255)], fill=(225, 228, 232), width=1)
    draw.line([(255, 0), (255, 255)], fill=(225, 228, 232), width=1)
    # Offline text
    text = "Offline Map Area"
    draw.text((80, 120), text, fill=(160, 165, 175))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

OFFLINE_PLACEHOLDER_PNG = create_offline_tile()

class TileServerHandler(http.server.SimpleHTTPRequestHandler):
    db: Optional[Database] = None
    is_offline_mode: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Handle tile requests: /tiles/{z}/{x}/{y}.png
        if path.startswith("/tiles/"):
            self.handle_tile_request(path, parsed.query)
            return

        # Default static file serving from frontend directory
        super().do_GET()

    def handle_tile_request(self, path: str, query_str: str):
        try:
            # Parse /tiles/{z}/{x}/{y}.png
            parts = path.strip("/").split("/")
            if len(parts) != 4:
                self.send_error(400, "Invalid tile path format")
                return

            _, z_str, x_str, y_file = parts
            z = int(z_str)
            x = int(x_str)
            y = int(y_file.split(".")[0])

            query_params = urllib.parse.parse_qs(query_str)
            layer = query_params.get("layer", ["standard"])[0]
            force_offline = query_params.get("offline", ["0"])[0] == "1"

            # 1. Check local SQLite cache first
            if self.db:
                cached_data = self.db.get_tile(z, x, y)
                if cached_data:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(cached_data)))
                    self.send_header("Cache-Control", "public, max-age=31536000")
                    self.end_headers()
                    self.wfile.write(cached_data)
                    return

            # 2. If in offline mode or force_offline, serve offline placeholder
            if self.is_offline_mode or force_offline or layer == "offline_only":
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(OFFLINE_PLACEHOLDER_PNG)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(OFFLINE_PLACEHOLDER_PNG)
                return

            # 3. If online mode allowed, fetch from upstream OSM
            upstream_url = self.get_upstream_url(layer, z, x, y)
            req = urllib.request.Request(
                upstream_url,
                headers={"User-Agent": USER_AGENT}
            )

            with urllib.request.urlopen(req, timeout=8.0) as resp:
                if resp.status == 200:
                    data = resp.read()
                    # Cache to SQLite database in background
                    if self.db:
                        self.db.save_tile(z, x, y, data)

                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    self.wfile.write(data)
                    return

        except Exception as e:
            logger.debug(f"Tile fetch fallback for {path}: {e}")

        # Fallback to offline placeholder if upstream fetch fails
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(OFFLINE_PLACEHOLDER_PNG)))
        self.end_headers()
        self.wfile.write(OFFLINE_PLACEHOLDER_PNG)

    def get_upstream_url(self, layer: str, z: int, x: int, y: int) -> str:
        if layer == "carto_dark":
            return CARTO_DARK_SERVER.format(z=z, x=x, y=y)
        elif layer == "carto_light":
            return CARTO_LIGHT_SERVER.format(z=z, x=x, y=y)
        else:
            # Standard OSM with server rotation
            idx = (x + y) % len(OSM_TILE_SERVERS)
            return OSM_TILE_SERVERS[idx].format(z=z, x=x, y=y)

    def log_message(self, format, *args):
        # Suppress spammy HTTP access logs in console
        pass


class LocalTileServer:
    def __init__(self, db: Database, host: str = SERVER_HOST, port: int = SERVER_DEFAULT_PORT):
        self.db = db
        self.host = host
        self.port = port
        self.httpd: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> int:
        """Starts local tile HTTP server on available port."""
        handler_class = TileServerHandler
        handler_class.db = self.db

        for p in range(self.port, self.port + 100):
            try:
                self.httpd = socketserver.TCPServer((self.host, p), handler_class)
                self.port = p
                break
            except OSError:
                continue

        if not self.httpd:
            raise RuntimeError(f"Could not bind local tile server to {self.host}:{self.port}")

        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"Local tile server started at http://{self.host}:{self.port}")
        return self.port

    def set_offline_mode(self, is_offline: bool):
        TileServerHandler.is_offline_mode = is_offline

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            logger.info("Local tile server stopped.")
