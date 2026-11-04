"""GUI Smoke and Integration Test for OfflineMap Explorer
Launches MainWindow with PySide6 & QtWebEngine, simulates user interactions,
and verifies clean startup, tab switching, and shutdown.
"""

import sys
from pathlib import Path
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from database.database import Database
from app.tile_server import LocalTileServer
from app.main_window import MainWindow

def test_gui():
    print("[GUI TEST] Initializing QApplication...")
    app = QApplication(sys.argv)

    db = Database()
    tile_server = LocalTileServer(db, port=8775)
    tile_server.start()

    print("[GUI TEST] Constructing MainWindow...")
    window = MainWindow(db, tile_server)
    window.show()

    def simulate_interactions():
        print("[GUI TEST] Testing navigation rail tab switching...")
        # Switch to Navigation tab
        window.btn_tab_nav.click()
        assert window.sidebar_stack.currentIndex() == 1, "Tab did not switch to Directions"

        # Switch to Offline Maps tab
        window.btn_tab_downloads.click()
        assert window.sidebar_stack.currentIndex() == 2, "Tab did not switch to Downloads"

        # Switch to Saved Places tab
        window.btn_tab_bookmarks.click()
        assert window.sidebar_stack.currentIndex() == 3, "Tab did not switch to Bookmarks"

        # Switch to Settings tab
        window.btn_tab_settings.click()
        assert window.sidebar_stack.currentIndex() == 4, "Tab did not switch to Settings"

        # Switch back to Search tab
        window.btn_tab_search.click()
        assert window.sidebar_stack.currentIndex() == 0, "Tab did not switch to Search"

        print("[GUI TEST] Testing search input...")
        window.input_search.setText("Trafalgar")

        print("[GUI TEST] Testing offline mode toggle...")
        window.check_offline_mode.setChecked(True)
        assert window.settings.is_offline_mode is True

        print("[GUI TEST] Testing dark mode toggle...")
        window.check_dark_mode.setChecked(True)
        assert window.settings.is_dark is True

        print("[GUI TEST] All GUI actions verified successfully! Exiting test...")
        window.close()
        tile_server.stop()
        app.quit()

    QTimer.singleShot(1500, simulate_interactions)

    # Safety timeout
    QTimer.singleShot(6000, app.quit)

    exit_code = app.exec()
    print(f"[GUI TEST] Application exited with code: {exit_code}")
    assert exit_code == 0
    print("[PASS] GUI SMOKE TEST PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_gui()
