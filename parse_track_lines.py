"""
Parse HURDAT2 into polyline segments — one line per 6-hour step.
Each segment carries the intensity at that moment, enabling
color-by-category rendering that shifts along the storm path.
Output as GeoJSON for direct AGOL upload.
"""

import json
from datetime import datetime

INPUT = "hurdat2-raw.txt"
OUTPUT = "atlantic_hurricane_track_segments.geojson"

def parse_coord(val):
    val = val.strip()
    direction = val[-1]
    num = float(val[:-1])
    if direction in ('S', 'W'):
        num = -num
    return num

def saffir_simpson(wind_kt):
    if wind_kt >= 137: return 5
    if wind_kt >= 113: return 4
    if wind_kt >= 96:  return 3
    if wind_kt >= 83:  return 2
    if wind_kt >= 64:  return 1
    if wind_kt >= 34:  return 0
    return -1

def category_label(cat):
    labels = {-1: "TD", 0: "TS", 1: "Cat 1", 2: "Cat 2", 3: "Cat 3", 4: "Cat 4", 5: "Cat 5"}
    return labels.get(cat, "Unknown")

# Parse all observations grouped by storm
storms = {}
current_id = None
current_name = None

with open(INPUT, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]

        if len(parts) == 4 and parts[0][:2] == "AL":
            current_id = parts[0]
            current_name = parts[1] if parts[1] else "UNNAMED"
            storms[current_id] = {"name": current_name, "obs": []}
            continue

        try:
            dt = datetime.strptime(parts[0] + parts[1].zfill(4), "%Y%m%d%H%M")
            lat = parse_coord(parts[4])
            lon = parse_coord(parts[5])
            wind = int(parts[6]) if parts[6] != "-999" else 0
            pres = int(parts[7]) if parts[7] != "-999" else None
            record_id = parts[2]
            status = parts[3]

            storms[current_id]["obs"].append({
                "dt": dt, "lat": lat, "lon": lon,
                "wind": wind, "pres": pres,
                "record_id": record_id, "status": status,
            })
        except (ValueError, IndexError):
            continue

# Build line segments: each consecutive pair of observations = one line
features = []
seg_count = 0

for storm_id, storm in storms.items():
    obs = storm["obs"]
    name = storm["name"]
    if len(obs) < 2:
        continue

    # Get storm-level peak category for filtering
    peak_wind = max(o["wind"] for o in obs)
    peak_cat = saffir_simpson(peak_wind)

    for i in range(len(obs) - 1):
        o1 = obs[i]
        o2 = obs[i + 1]

        # Use the intensity at the START of the segment
        wind = o1["wind"]
        cat = saffir_simpson(wind)

        coords = [[o1["lon"], o1["lat"]], [o2["lon"], o2["lat"]]]

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
            "properties": {
                "storm_id": storm_id,
                "name": name,
                "year": o1["dt"].year,
                "month": o1["dt"].month,
                "datetime": o1["dt"].strftime("%Y-%m-%d %H:%M"),
                "date": o1["dt"].strftime("%Y-%m-%d"),
                "status": o1["status"],
                "is_landfall": 1 if o1["record_id"] == "L" else 0,
                "wind_kt": wind if wind else None,
                "wind_mph": int(wind * 1.151) if wind else None,
                "pressure_mb": o1["pres"],
                "category_num": cat,
                "category": category_label(cat),
                "is_hurricane": 1 if cat >= 1 else 0,
                "is_major": 1 if cat >= 3 else 0,
                "peak_category_num": peak_cat,
                "peak_category": category_label(peak_cat),
                "segment_num": i + 1,
            }
        }
        features.append(feature)
        seg_count += 1

geojson = {
    "type": "FeatureCollection",
    "features": features,
}

with open(OUTPUT, "w") as f:
    json.dump(geojson, f)

import os
size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)

print(f"=== Track Segments Built ===")
print(f"Total segments: {seg_count:,}")
print(f"Storms with tracks: {len([s for s in storms.values() if len(s['obs']) >= 2]):,}")
print(f"File size: {size_mb:.1f} MB")
print(f"Output: {OUTPUT}")

# Category distribution
from collections import Counter
cat_counts = Counter(f["properties"]["category"] for f in features)
print(f"\nSegments by intensity:")
for label in ["TD", "TS", "Cat 1", "Cat 2", "Cat 3", "Cat 4", "Cat 5"]:
    print(f"  {label:8s}: {cat_counts.get(label, 0):,}")
