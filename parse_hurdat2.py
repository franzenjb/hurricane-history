"""
Parse HURDAT2 into a clean CSV: one row per named storm.
Focus on last 50 years (1976-2025) for calendar heat chart use.
Includes: storm ID, name, start date, peak category, max wind, min pressure, duration.
"""

import csv
from datetime import datetime, timedelta

INPUT = "hurdat2-raw.txt"
OUTPUT_ALL = "atlantic_hurricanes_all.csv"
OUTPUT_50YR = "atlantic_hurricanes_50yr.csv"

def saffir_simpson(wind_kt):
    """Classify by max sustained wind (knots)."""
    if wind_kt >= 137: return 5
    if wind_kt >= 113: return 4
    if wind_kt >= 96:  return 3
    if wind_kt >= 83:  return 2
    if wind_kt >= 64:  return 1
    if wind_kt >= 34:  return 0  # Tropical Storm
    return -1  # Tropical Depression

def category_label(cat):
    labels = {-1: "TD", 0: "TS", 1: "Cat 1", 2: "Cat 2", 3: "Cat 3", 4: "Cat 4", 5: "Cat 5"}
    return labels.get(cat, "Unknown")

def is_major(cat):
    return 1 if cat >= 3 else 0

storms = []

with open(INPUT, "r") as f:
    current_storm = None
    observations = []

    for line in f:
        line = line.strip()
        if not line:
            continue

        parts = [p.strip() for p in line.split(",")]

        # Header row: storm ID, name, num_entries
        if len(parts) == 4 and parts[0][:2] == "AL":
            # Save previous storm
            if current_storm and observations:
                max_wind = max(o["wind"] for o in observations)
                min_pres = min(o["pres"] for o in observations if o["pres"] > 0)
                first_date = observations[0]["dt"]
                last_date = observations[-1]["dt"]
                duration_hours = (last_date - first_date).total_seconds() / 3600

                cat = saffir_simpson(max_wind)

                # Count landfall entries
                landfalls = sum(1 for o in observations if o["record_id"] == "L")

                storms.append({
                    "storm_id": current_storm["id"],
                    "year": first_date.year,
                    "month": first_date.month,
                    "month_name": first_date.strftime("%B"),
                    "name": current_storm["name"],
                    "start_date": first_date.strftime("%Y-%m-%d"),
                    "end_date": last_date.strftime("%Y-%m-%d"),
                    "duration_hours": int(duration_hours),
                    "max_wind_kt": max_wind,
                    "max_wind_mph": int(max_wind * 1.151),
                    "min_pressure_mb": min_pres if min_pres < 9999 else None,
                    "category_num": cat,
                    "category": category_label(cat),
                    "is_hurricane": 1 if cat >= 1 else 0,
                    "is_major": is_major(cat),
                    "landfalls": landfalls,
                    "observations": len(observations),
                })

            current_storm = {"id": parts[0], "name": parts[1] if parts[1] else "UNNAMED"}
            observations = []
        else:
            # Detail row
            try:
                dt = datetime.strptime(parts[0] + parts[1].zfill(4), "%Y%m%d%H%M")
                wind = int(parts[6]) if parts[6] != "-999" else 0
                pres = int(parts[7]) if parts[7] != "-999" else 9999
                record_id = parts[2]
                status = parts[3]

                observations.append({
                    "dt": dt,
                    "wind": wind,
                    "pres": pres,
                    "record_id": record_id,
                    "status": status,
                })
            except (ValueError, IndexError):
                continue

    # Don't forget the last storm
    if current_storm and observations:
        max_wind = max(o["wind"] for o in observations)
        min_pres = min(o["pres"] for o in observations if o["pres"] > 0)
        first_date = observations[0]["dt"]
        last_date = observations[-1]["dt"]
        duration_hours = (last_date - first_date).total_seconds() / 3600
        cat = saffir_simpson(max_wind)
        landfalls = sum(1 for o in observations if o["record_id"] == "L")

        storms.append({
            "storm_id": current_storm["id"],
            "year": first_date.year,
            "month": first_date.month,
            "month_name": first_date.strftime("%B"),
            "name": current_storm["name"],
            "start_date": first_date.strftime("%Y-%m-%d"),
            "end_date": last_date.strftime("%Y-%m-%d"),
            "duration_hours": int(duration_hours),
            "max_wind_kt": max_wind,
            "max_wind_mph": int(max_wind * 1.151),
            "min_pressure_mb": min_pres if min_pres < 9999 else None,
            "category_num": cat,
            "category": category_label(cat),
            "is_hurricane": 1 if cat >= 1 else 0,
            "is_major": is_major(cat),
            "landfalls": landfalls,
            "observations": len(observations),
        })

# Write all storms
fields = ["storm_id", "year", "month", "month_name", "name", "start_date", "end_date",
          "duration_hours", "max_wind_kt", "max_wind_mph", "min_pressure_mb",
          "category_num", "category", "is_hurricane", "is_major", "landfalls", "observations"]

with open(OUTPUT_ALL, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(storms)

# Write 50-year subset (1976-2025) — hurricanes only (cat 1+)
recent = [s for s in storms if s["year"] >= 1976 and s["is_hurricane"] == 1]
with open(OUTPUT_50YR, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(recent)

# Summary stats
print(f"\n=== HURDAT2 Parse Complete ===")
print(f"Total storms (all years): {len(storms)}")
print(f"Year range: {storms[0]['year']} - {storms[-1]['year']}")
print(f"\n--- Last 50 years (1976-2025) ---")
recent_all = [s for s in storms if s["year"] >= 1976]
hurricanes = [s for s in recent_all if s["is_hurricane"] == 1]
majors = [s for s in recent_all if s["is_major"] == 1]
print(f"Total named storms: {len(recent_all)}")
print(f"Hurricanes (Cat 1+): {len(hurricanes)}")
print(f"Major hurricanes (Cat 3+): {len(majors)}")
print(f"\nBy month (hurricanes only):")
from collections import Counter
month_counts = Counter(s["month_name"] for s in hurricanes)
for m in ["May", "June", "July", "August", "September", "October", "November", "December"]:
    print(f"  {m:12s}: {month_counts.get(m, 0)}")

print(f"\nCat 5 storms (last 50 yrs):")
cat5s = [s for s in recent_all if s["category_num"] == 5]
for s in cat5s:
    print(f"  {s['year']} {s['name']:15s} {s['max_wind_kt']}kt  {s['start_date']}")

print(f"\nFiles written:")
print(f"  {OUTPUT_ALL} ({len(storms)} storms)")
print(f"  {OUTPUT_50YR} ({len(recent)} hurricanes)")
