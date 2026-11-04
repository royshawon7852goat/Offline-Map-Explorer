"""Turn-by-turn directions generator for OfflineMap Explorer
Calculates bearings, maneuver classifications, human-readable turn instructions,
and aggregate travel metrics.
"""

import math
from typing import List, Dict, Any, Tuple

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates initial compass bearing from point 1 to point 2 in degrees (0-360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360.0) % 360.0

def get_compass_direction(bearing: float) -> str:
    """Returns compass direction string (North, Northeast, etc.) for a given bearing."""
    directions = ["North", "Northeast", "East", "Southeast", "South", "Southwest", "West", "Northwest"]
    idx = int((bearing + 22.5) / 45.0) % 8
    return directions[idx]

def classify_maneuver(bearing_in: float, bearing_out: float) -> Tuple[str, str]:
    """Classifies turn maneuver and provides icon name based on change in bearing."""
    diff = (bearing_out - bearing_in + 180.0) % 360.0 - 180.0

    if abs(diff) <= 20.0:
        return "straight", "arrow-up"
    elif 20.0 < diff <= 45.0:
        return "slight_right", "arrow-up-right"
    elif 45.0 < diff <= 125.0:
        return "right", "arrow-right"
    elif 125.0 < diff <= 165.0:
        return "sharp_right", "corner-up-right"
    elif -45.0 <= diff < -20.0:
        return "slight_left", "arrow-up-left"
    elif -125.0 <= diff < -45.0:
        return "left", "arrow-left"
    elif -165.0 <= diff < -125.0:
        return "sharp_left", "corner-up-left"
    else:
        return "uturn", "rotate-ccw"

def format_distance(meters: float) -> str:
    if meters < 1000:
        return f"{int(round(meters))} m"
    else:
        return f"{round(meters / 1000.0, 1)} km"

def format_duration(seconds: float) -> str:
    mins = int(round(seconds / 60.0))
    if mins < 60:
        return f"{max(1, mins)} min"
    hours = mins // 60
    rem_mins = mins % 60
    return f"{hours} hr {rem_mins} min" if rem_mins > 0 else f"{hours} hr"

def generate_turn_instructions(route_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generates detailed, grouped turn-by-turn instructions from road segments.
    Each segment contains:
    {
        'geometry': [(lat, lng), ...],
        'name': str,
        'length_m': float,
        'duration_s': float,
        'road_type': str
    }
    """
    if not route_segments:
        return []

    instructions = []
    
    # First step: Departure
    first_seg = route_segments[0]
    first_geom = first_seg.get("geometry", [])
    if len(first_geom) >= 2:
        initial_bearing = calculate_bearing(
            first_geom[0][0], first_geom[0][1],
            first_geom[1][0], first_geom[1][1]
        )
    else:
        initial_bearing = 0.0

    compass_dir = get_compass_direction(initial_bearing)
    street_name = first_seg.get("name") or "the road"

    current_instruction = {
        "step_index": 0,
        "type": "depart",
        "icon": "navigation",
        "instruction": f"Head {compass_dir} on {street_name}",
        "street_name": street_name,
        "distance_m": first_seg.get("length_m", 0.0),
        "duration_s": first_seg.get("duration_s", 0.0),
        "lat": first_geom[0][0] if first_geom else 0.0,
        "lng": first_geom[0][1] if first_geom else 0.0,
    }

    prev_bearing_out = initial_bearing

    for i in range(1, len(route_segments)):
        seg = route_segments[i]
        seg_geom = seg.get("geometry", [])
        if len(seg_geom) < 2:
            current_instruction["distance_m"] += seg.get("length_m", 0.0)
            current_instruction["duration_s"] += seg.get("duration_s", 0.0)
            continue

        bearing_in = prev_bearing_out
        bearing_out = calculate_bearing(
            seg_geom[0][0], seg_geom[0][1],
            seg_geom[1][0], seg_geom[1][1]
        )
        prev_bearing_out = bearing_out

        seg_name = seg.get("name") or "unnamed road"
        maneuver, icon = classify_maneuver(bearing_in, bearing_out)

        # Merge segments if same street name and continue straight
        if maneuver == "straight" and seg_name == current_instruction["street_name"]:
            current_instruction["distance_m"] += seg.get("length_m", 0.0)
            current_instruction["duration_s"] += seg.get("duration_s", 0.0)
        else:
            # Finalize current instruction
            current_instruction["distance_text"] = format_distance(current_instruction["distance_m"])
            current_instruction["duration_text"] = format_duration(current_instruction["duration_s"])
            instructions.append(current_instruction)

            # Build human readable text
            if maneuver == "straight":
                text = f"Continue onto {seg_name}"
            elif maneuver == "slight_right":
                text = f"Slight right onto {seg_name}"
            elif maneuver == "right":
                text = f"Turn right onto {seg_name}"
            elif maneuver == "sharp_right":
                text = f"Sharp right onto {seg_name}"
            elif maneuver == "slight_left":
                text = f"Slight left onto {seg_name}"
            elif maneuver == "left":
                text = f"Turn left onto {seg_name}"
            elif maneuver == "sharp_left":
                text = f"Sharp left onto {seg_name}"
            elif maneuver == "uturn":
                text = f"Make a U-turn onto {seg_name}"
            else:
                text = f"Proceed onto {seg_name}"

            current_instruction = {
                "step_index": len(instructions),
                "type": maneuver,
                "icon": icon,
                "instruction": text,
                "street_name": seg_name,
                "distance_m": seg.get("length_m", 0.0),
                "duration_s": seg.get("duration_s", 0.0),
                "lat": seg_geom[0][0],
                "lng": seg_geom[0][1],
            }

    # Finalize last driving step
    current_instruction["distance_text"] = format_distance(current_instruction["distance_m"])
    current_instruction["duration_text"] = format_duration(current_instruction["duration_s"])
    instructions.append(current_instruction)

    # Add arrival step
    last_geom = route_segments[-1].get("geometry", [])
    dest_lat = last_geom[-1][0] if last_geom else 0.0
    dest_lng = last_geom[-1][1] if last_geom else 0.0

    instructions.append({
        "step_index": len(instructions),
        "type": "arrive",
        "icon": "map-pin",
        "instruction": "You have arrived at your destination",
        "street_name": "Destination",
        "distance_m": 0.0,
        "duration_s": 0.0,
        "distance_text": "0 m",
        "duration_text": "0 min",
        "lat": dest_lat,
        "lng": dest_lng,
    })

    return instructions
