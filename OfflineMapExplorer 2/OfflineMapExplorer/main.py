"""OfflineMap Explorer - Entry Point
Launches the desktop offline map and navigation application.
"""

import sys
import logging
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtWidgets import QApplication

from config import APP_NAME, APP_ORGANIZATION
from database.database import Database
from app.tile_server import LocalTileServer
from app.main_window import MainWindow

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
        datefmt="%H:%M:%S"
    )

def main():
    setup_logging()
    logger = logging.getLogger("OfflineMap.Main")
    logger.info(f"Starting {APP_NAME}...")

    # Qt Application setup
    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setOrganizationName(APP_ORGANIZATION)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)

    # 1. Initialize SQLite Database
    db = Database()

    # 2. Start Local HTTP Server for Frontend & Tile Caching
    tile_server = LocalTileServer(db)
    tile_server.start()

    # 3. Create Main Application Window
    window = MainWindow(db, tile_server)
    window.show()

    # 4. Clean exit handler
    def cleanup():
        logger.info("Shutting down OfflineMap Explorer...")
        tile_server.stop()

    app.aboutToQuit.connect(cleanup)

    exit_code = app.exec()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
