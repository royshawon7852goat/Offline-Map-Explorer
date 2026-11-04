"""Core Verification Tests for OfflineMap Explorer
Tests Database, Offline Routing, FTS5 Search, and Tile Server.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import DB_PATH
from database.database import Database
from routing.route_engine import OfflineRouteEngine
from app.tile_server import LocalTileServer

def test_all():
    print("1. Initializing Database...")
    db = Database()
    stats = db.get_storage_stats()
    print("   Database initialized. Storage stats:", stats)

    print("\n2. Initializing Offline Routing Engine...")
    engine = OfflineRouteEngine(db)
    print(f"   Graph nodes: {len(engine.graph.nodes)}, edges: {len(engine.graph.edges)}")

    print("\n3. Testing Offline Route Calculation:")
    # Big Ben (51.5007, -0.1246) to Covent Garden (51.5120, -0.1200)
    route = engine.calculate_route(
        start_lat=51.5007,
        start_lng=-0.1246,
        dest_lat=51.5120,
        dest_lng=-0.1200,
        mode="driving"
    )
    assert route["status"] == "ok", f"Route calculation failed: {route.get('message')}"
    prim = route["primary_route"]
    print(f"   Route Status: {route['status']}")
    print(f"   Distance: {prim['distance_text']}")
    print(f"   Duration: {prim['duration_text']}")
    print(f"   Turn Steps ({len(prim['turn_steps'])}):")
    for s in prim["turn_steps"]:
        print(f"     - {s['instruction']} [{s.get('distance_text', '')}]")

    print("\n4. Testing Alternative Route Generation:")
    if route.get("alternative_route"):
        alt = route["alternative_route"]
        print(f"   Alternative route found! Distance: {alt['distance_text']}, Duration: {alt['duration_text']}")
    else:
        print("   Single optimal path found.")

    print("\n5. Testing Walking Mode Route:")
    walk_route = engine.calculate_route(
        start_lat=51.5007,
        start_lng=-0.1246,
        dest_lat=51.5080,
        dest_lng=-0.1281,
        mode="walking"
    )
    assert walk_route["status"] == "ok"
    print(f"   Walking Route: {walk_route['primary_route']['distance_text']} in {walk_route['primary_route']['duration_text']}")

    print("\n6. Testing Offline Full-Text Search (FTS5):")
    queries = ["Trafalgar", "Covent", "Big Ben", "Bridge"]
    for q in queries:
        results = db.search_pois(q)
        print(f"   Query '{q}': found {len(results)} matches -> {[r['name'] for r in results[:2]]}")

    print("\n7. Testing Local Tile Server...")
    server = LocalTileServer(db, port=8772)
    bound_port = server.start()
    print(f"   Tile server listening on port {bound_port}")
    server.stop()
    print("   Tile server stopped.")

    print("\n[PASS] ALL BACKEND AND ROUTING UNIT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all()
