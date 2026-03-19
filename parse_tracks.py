"""
Parse HURDAT2 into track points CSV with lat/lon.
Every 6-hour observation becomes a point. Includes landfall flag.
"""

import csv
from datetime import datetime

INPUT = "hurdat2-raw.txt"
OUTPUT = "atlantic_hurricane_tracks.csv"

def parse_coord(val):
    """Convert '28.0N' or '94.8W' to decimal degrees."""
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
    if wind_kt >= 34:  return 0  # TS
    return -1  # TD

def category_label(cat):
    labels = {-1: "TD", 0: "TS", 1: "Cat 1", 2: "Cat 2", 3: "Cat 3", 4: "Cat 4", 5: "Cat 5"}
    return labels.get(cat, "Unknown")

rows = []
current_id = None
current_name = None

with open(INPUT, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        parts = [p.strip() for p in line.split(",")]

        # Header row
        if len(parts) == 4 and parts[0][:2] == "AL":
            current_id = parts[0]
            current_name = parts[1] if parts[1] else "UNNAMED"
            continue

        # Detail row
        try:
            dt_str = parts[0] + parts[1].zfill(4)
            dt = datetime.strptime(dt_str, "%Y%m%d%H%M")
            record_id = parts[2]
            status = parts[3]
            lat = parse_coord(parts[4])
            lon = parse_coord(parts[5])
            wind = int(parts[6]) if parts[6] != "-999" else None
            pres = int(parts[7]) if parts[7] != "-999" else None

            cat = saffir_simpson(wind) if wind else -1

            rows.append({
                "storm_id": current_id,
                "name": current_name,
                "year": dt.year,
                "datetime": dt.strftime("%Y-%m-%d %H:%M"),
                "date": dt.strftime("%Y-%m-%d"),
                "month": dt.month,
                "status": status,
                "is_landfall": 1 if record_id == "L" else 0,
                "latitude": lat,
                "longitude": lon,
                "wind_kt": wind if wind else "",
                "wind_mph": int(wind * 1.151) if wind else "",
                "pressure_mb": pres if pres else "",
                "category_num": cat,
                "category": category_label(cat),
                "is_hurricane": 1 if cat >= 1 else 0,
                "is_major": 1 if cat >= 3 else 0,
            })
        except (ValueError, IndexError):
            continue

fields = ["storm_id", "name", "year", "datetime", "date", "month",
          "status", "is_landfall", "latitude", "longitude",
          "wind_kt", "wind_mph", "pressure_mb",
          "category_num", "category", "is_hurricane", "is_major"]

with open(OUTPUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

# Stats
landfalls = sum(1 for r in rows if r["is_landfall"] == 1)
storms = len(set(r["storm_id"] for r in rows))
print(f"=== Track Points Parsed ===")
print(f"Total observations: {len(rows):,}")
print(f"Unique storms: {storms:,}")
print(f"Landfall points: {landfalls:,}")
print(f"Year range: {rows[0]['year']}-{rows[-1]['year']}")
print(f"Output: {OUTPUT}")

# File size
import os
size_mb = os.path.getsize(OUTPUT) / (1024 * 1024)
print(f"File size: {size_mb:.1f} MB")
