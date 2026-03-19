#!/usr/bin/env python3
"""
Generate narratives for all 2,004 Atlantic storms from HURDAT2 raw data.
Adds 'narrative' and 'is_retired' columns to the CSV files.
"""

import csv
import math
from datetime import datetime, timedelta
from collections import OrderedDict

HURDAT2_FILE = "/Users/jefffranzen/hurricane-history/hurdat2-raw.txt"
ALL_CSV = "/Users/jefffranzen/hurricane-history/atlantic_hurricanes_all.csv"
FIFTY_CSV = "/Users/jefffranzen/hurricane-history/atlantic_hurricanes_50yr.csv"

# Retired Atlantic hurricane names (case-insensitive match)
RETIRED_NAMES = {n.strip().upper() for n in """
Agnes, Alicia, Allen, Allison, Andrew, Anita, Audrey, Barry, Betsy, Beulah,
Bob, Camille, Carla, Carmen, Carol, Celia, Cesar, Charley, Cleo, Connie,
David, Dean, Dennis, Diana, Diane, Donna, Dorian, Dora, Edna, Elena, Eloise,
Erika, Eta, Fabian, Fay, Felix, Fiona, Flora, Florence, Floyd, Fran, Frances,
Frederic, Georges, Gilbert, Gloria, Gordon, Gustav, Harvey, Hazel, Helene,
Hilda, Hugo, Ian, Ike, Inez, Ingrid, Ione, Iota, Irene, Iris, Irma, Isabel,
Isidore, Ivan, Janet, Jeanne, Joaquin, Joan, Juan, Katrina, Keith, Klaus,
Larry, Laura, Lee, Lenny, Lili, Lorenzo, Luis, Marilyn, Maria, Matthew,
Michael, Michelle, Mitch, Milton, Mu, Nana, Nate, Nicole, Noel, Nora, Opal,
Otis, Otto, Paloma, Patricia, Phi, Rita, Roxanne, Sandy, Stan, Tomas,
Ida, Grace, Elsa, Nicholas, Philippe, Tammy, Beryl, Debby, Francine, Kirk,
Rafael
""".replace("\n", ",").split(",")} - {""}

# Saffir-Simpson scale thresholds (knots)
def saffir_simpson(wind_kt):
    if wind_kt >= 137: return 5
    if wind_kt >= 113: return 4
    if wind_kt >= 96: return 3
    if wind_kt >= 83: return 2
    if wind_kt >= 64: return 1
    return 0

def category_name(cat):
    if cat == 0: return "tropical storm"
    return f"Category {cat} hurricane"

def get_basin_area(lat, lon):
    """Convert lat/lon to a general Atlantic basin area name."""
    # lon is negative for west
    if 18 <= lat <= 31 and -98 <= lon <= -82:
        return "the Gulf of Mexico"
    if 9 <= lat <= 22 and -88 <= lon <= -60:
        return "the Caribbean Sea"
    if 8 <= lat <= 25 and -35 <= lon <= -15:
        return "the eastern Atlantic near the Cape Verde Islands"
    if 10 <= lat <= 35 and -65 <= lon <= -35:
        return "the central Atlantic"
    if 25 <= lat <= 45 and -82 <= lon <= -65:
        return "the western Atlantic off the U.S. East Coast"
    if 20 <= lat <= 40 and -82 <= lon <= -65:
        return "the western Atlantic"
    return "the open Atlantic"

def get_landfall_area(lat, lon):
    """More specific area for landfall locations."""
    if 25 <= lat <= 31 and -98 <= lon <= -88:
        return "the northern Gulf Coast"
    if 25 <= lat <= 31 and -88 <= lon <= -80:
        return "the Florida Gulf Coast" if lat < 28 else "the northern Gulf Coast"
    if 24 <= lat <= 28 and -83 <= lon <= -79:
        return "southern Florida"
    if 28 <= lat <= 35 and -82 <= lon <= -75:
        return "the southeastern U.S. coast"
    if 35 <= lat <= 42 and -78 <= lon <= -70:
        return "the northeastern U.S. coast"
    if 18 <= lat <= 22 and -98 <= lon <= -86:
        return "the Yucatan Peninsula"
    if 17 <= lat <= 23 and -86 <= lon <= -72:
        return "the Caribbean islands"
    if 30 <= lat <= 36 and -98 <= lon <= -88:
        return "the Texas or Louisiana coast"
    return get_basin_area(lat, lon)

def compute_direction(lat1, lon1, lat2, lon2):
    """Describe the general track direction from start to end."""
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    if abs(dlat) < 1 and abs(dlon) < 1:
        return "remained nearly stationary"

    angle = math.degrees(math.atan2(dlon, dlat))  # dlon=x, dlat=y

    # Compass directions
    if -22.5 <= angle < 22.5:
        return "tracked northward"
    elif 22.5 <= angle < 67.5:
        return "tracked northeastward"
    elif 67.5 <= angle < 112.5:
        return "tracked eastward"
    elif 112.5 <= angle < 157.5:
        return "tracked southeastward"
    elif angle >= 157.5 or angle < -157.5:
        return "tracked southward"
    elif -157.5 <= angle < -112.5:
        return "tracked southwestward"
    elif -112.5 <= angle < -67.5:
        return "tracked westward"
    elif -67.5 <= angle < -22.5:
        return "tracked northwestward"
    return "tracked across the basin"

def detect_recurvature(lats, lons):
    """Check if storm recurved (started west, then turned northeast)."""
    if len(lats) < 6:
        return False
    mid = len(lats) // 2
    # First half moving west, second half moving east/northeast
    first_dlon = lons[mid] - lons[0]
    second_dlon = lons[-1] - lons[mid]
    second_dlat = lats[-1] - lats[mid]
    return first_dlon < -3 and second_dlon > 2 and second_dlat > 2

def format_date(datestr):
    """Format YYYYMMDD to 'Month Day, Year'."""
    dt = datetime.strptime(datestr, "%Y%m%d")
    return dt.strftime("%B %d, %Y").replace(" 0", " ")

def format_date_short(datestr):
    """Format YYYYMMDD to 'Month Day'."""
    dt = datetime.strptime(datestr, "%Y%m%d")
    return dt.strftime("%B %d").replace(" 0", " ")

# ── Parse HURDAT2 ──────────────────────────────────────────────────

def parse_hurdat2(filepath):
    """Parse HURDAT2 into dict of storm_id -> observation list."""
    storms = OrderedDict()
    current_id = None
    current_name = None

    with open(filepath, "r") as f:
        for line in f:
            line = line.rstrip()
            parts = [p.strip() for p in line.split(",")]

            # Header line: storm_id, name, num_observations
            if len(parts) >= 3 and parts[0].startswith("AL"):
                # Check if it's a header (has alpha chars after AL + digits)
                candidate_id = parts[0]
                if len(candidate_id) == 8 and candidate_id[2:4].isdigit():
                    current_id = candidate_id
                    current_name = parts[1].strip()
                    storms[current_id] = {
                        "name": current_name,
                        "observations": []
                    }
                    continue

            # Data line
            if current_id and len(parts) >= 8:
                datestr = parts[0].strip()
                timestr = parts[1].strip()
                record_id = parts[2].strip()
                status = parts[3].strip()

                # Parse lat
                lat_str = parts[4].strip()
                lat = float(lat_str[:-1])
                if lat_str.endswith("S"):
                    lat = -lat

                # Parse lon
                lon_str = parts[5].strip()
                lon = float(lon_str[:-1])
                if lon_str.endswith("W"):
                    lon = -lon

                wind = int(parts[6].strip()) if parts[6].strip() not in ("-999", "") else -999
                pressure = int(parts[7].strip()) if parts[7].strip() not in ("-999", "") else -999

                storms[current_id]["observations"].append({
                    "date": datestr,
                    "time": timestr,
                    "record_id": record_id,
                    "status": status,
                    "lat": lat,
                    "lon": lon,
                    "wind": wind,
                    "pressure": pressure,
                })

    return storms

# ── Generate narrative ──────────────────────────────────────────────

def generate_narrative(storm_id, obs_list, name, csv_row):
    """Generate a natural English narrative for one storm."""

    if not obs_list:
        return "No detailed track data available for this storm."

    # Extract basic info from CSV row
    year = csv_row["year"]
    cat_num = int(csv_row["category_num"]) if csv_row["category_num"] else 0
    max_wind_kt = int(csv_row["max_wind_kt"]) if csv_row["max_wind_kt"] else 0
    max_wind_mph = int(csv_row["max_wind_mph"]) if csv_row["max_wind_mph"] else 0
    is_major = int(csv_row["is_major"]) if csv_row["is_major"] else 0
    is_hurricane = int(csv_row["is_hurricane"]) if csv_row["is_hurricane"] else 0
    num_landfalls = int(csv_row["landfalls"]) if csv_row["landfalls"] else 0
    duration_hours = int(csv_row["duration_hours"]) if csv_row["duration_hours"] else 0
    min_pressure = csv_row.get("min_pressure_mb", "")
    category_label = csv_row.get("category", "")

    # Compute from observations
    lats = [o["lat"] for o in obs_list]
    lons = [o["lon"] for o in obs_list]
    winds = [o["wind"] for o in obs_list if o["wind"] > 0]
    pressures = [o["pressure"] for o in obs_list if o["pressure"] > 0]

    first_lat, first_lon = lats[0], lons[0]
    last_lat, last_lon = lats[-1], lons[-1]
    first_date = obs_list[0]["date"]
    last_date = obs_list[-1]["date"]

    # Peak intensity observation
    peak_obs = max(obs_list, key=lambda o: o["wind"] if o["wind"] > 0 else 0)
    peak_date = peak_obs["date"]
    peak_wind = peak_obs["wind"]
    peak_cat = saffir_simpson(peak_wind) if peak_wind > 0 else cat_num

    # Landfalls from observations
    landfall_obs = [o for o in obs_list if o["record_id"] == "L"]

    # Duration in days
    duration_days = duration_hours / 24.0 if duration_hours else len(obs_list) * 6 / 24.0

    # Min pressure from observations
    min_pres_val = min(pressures) if pressures else None
    if not min_pres_val and min_pressure and min_pressure not in ("", "-999"):
        try:
            min_pres_val = int(min_pressure)
        except ValueError:
            min_pres_val = None

    # Display name
    display_name = name if name != "UNNAMED" else f"Storm {storm_id}"
    if name == "UNNAMED":
        article = ""
        subject = f"The unnamed storm of {year} ({storm_id})"
        pronoun_subject = "The storm"
    else:
        # Named storms: "Hurricane X" or "Tropical Storm X"
        if is_hurricane:
            subject = f"Hurricane {name.title()}"
        else:
            subject = f"Tropical Storm {name.title()}"
        article = ""
        pronoun_subject = "The storm"

    # Determine if the storm recurved
    recurved = detect_recurvature(lats, lons)

    # Identify unique areas traversed (for richer narrative)
    areas_visited = []
    prev_area = None
    for o in obs_list:
        area = get_basin_area(o["lat"], o["lon"])
        if area != prev_area:
            areas_visited.append(area)
            prev_area = area

    # Compute rapid intensification (>30kt gain in 24h)
    rapid_intensification = False
    if len(obs_list) >= 4:
        for i in range(len(obs_list) - 4):
            w0 = obs_list[i]["wind"]
            w1 = obs_list[i + 4]["wind"]
            if w0 > 0 and w1 > 0 and (w1 - w0) >= 30:
                rapid_intensification = True
                break

    # Season context
    month_num = int(csv_row["month"]) if csv_row["month"] else 0
    season_context = ""
    if month_num in (1, 2, 3, 4, 5):
        season_context = "an unusual off-season system"
    elif month_num == 6:
        season_context = "an early-season storm"
    elif month_num == 12:
        season_context = "a late-season storm"
    elif month_num == 11:
        season_context = "a late-season system"

    # Latitude range for track extent
    lat_range = max(lats) - min(lats)
    lon_range = abs(max(lons) - min(lons))

    # Is target major (need longer narrative)?
    target_major = cat_num >= 3

    # Build the narrative
    sentences = []

    # Formation
    formation_area = get_basin_area(first_lat, first_lon)
    if season_context:
        sentences.append(f"{subject}, {season_context}, formed in {formation_area} on {format_date_short(first_date)}, {year}.")
    else:
        sentences.append(f"{subject} formed in {formation_area} on {format_date_short(first_date)}, {year}.")

    # Track description
    if recurved:
        sentences.append(f"It initially tracked westward through the Atlantic before recurving northeastward.")
    else:
        direction = compute_direction(first_lat, first_lon, last_lat, last_lon)
        sentences.append(f"The system {direction} during its lifetime.")

    # Areas traversed (for longer storms or major hurricanes)
    if len(areas_visited) >= 3 and (target_major or duration_days >= 5):
        unique_areas = []
        for a in areas_visited:
            if a not in unique_areas:
                unique_areas.append(a)
        if len(unique_areas) >= 3:
            area_list = ", ".join(unique_areas[:4])
            sentences.append(f"Over its lifetime, the storm traversed {area_list}.")
        elif len(unique_areas) == 2:
            sentences.append(f"The storm moved from {unique_areas[0]} into {unique_areas[1]}.")

    # Track extent for larger storms
    if target_major and lat_range > 15:
        sentences.append(f"The storm covered a vast area, spanning approximately {round(lat_range)} degrees of latitude.")
    elif target_major and lon_range > 30:
        sentences.append(f"It traversed a wide swath of the Atlantic, covering roughly {round(lon_range)} degrees of longitude.")

    # Intensification
    if peak_wind > 0 and peak_cat > 0:
        peak_mph = int(peak_wind * 1.151)
        sentences.append(
            f"It reached peak intensity as a {category_name(peak_cat)} on {format_date_short(peak_date)} "
            f"with maximum sustained winds of {peak_mph} mph ({peak_wind} kt)."
        )
    elif peak_wind > 0:
        peak_mph = int(peak_wind * 1.151)
        sentences.append(
            f"It reached peak intensity on {format_date_short(peak_date)} "
            f"with maximum sustained winds of {peak_mph} mph ({peak_wind} kt)."
        )

    # Rapid intensification
    if rapid_intensification and target_major:
        sentences.append("The storm underwent rapid intensification, with winds increasing by at least 35 mph within a 24-hour period.")

    # Minimum pressure
    if min_pres_val and min_pres_val > 0 and min_pres_val < 1010:
        sentences.append(f"The minimum central pressure was recorded at {min_pres_val} mb.")

    # Intensification history for major hurricanes
    if target_major:
        # Find when it first became a hurricane and when it reached peak
        first_hu = None
        for o in obs_list:
            if o["status"] in ("HU",) and o["wind"] >= 64:
                first_hu = o
                break
        if first_hu and first_hu["date"] != peak_date:
            sentences.append(
                f"The system first reached hurricane strength on {format_date_short(first_hu['date'])} "
                f"and continued to intensify over the following days."
            )

    # Landfalls
    if landfall_obs:
        for i, lf in enumerate(landfall_obs):
            area = get_landfall_area(lf["lat"], lf["lon"])
            lf_wind = lf["wind"] if lf["wind"] > 0 else 0
            lf_cat = saffir_simpson(lf_wind)
            if lf_wind > 0:
                lf_mph = int(lf_wind * 1.151)
                if lf_cat > 0:
                    sentences.append(
                        f"It made landfall near {area} on {format_date_short(lf['date'])} "
                        f"as a {category_name(lf_cat)} with winds of {lf_mph} mph."
                    )
                else:
                    sentences.append(
                        f"It made landfall near {area} on {format_date_short(lf['date'])} "
                        f"with winds of {lf_mph} mph."
                    )
            else:
                sentences.append(f"It made landfall near {area} on {format_date_short(lf['date'])}.")
            # Only detail first 2 landfalls to keep narrative concise
            if i >= 1 and len(landfall_obs) > 2:
                remaining = len(landfall_obs) - 2
                sentences.append(f"The storm made {remaining} additional landfall{'s' if remaining > 1 else ''} during its track.")
                break
    elif num_landfalls > 0:
        sentences.append("The storm made landfall during its track.")
    elif target_major:
        sentences.append("The storm remained over open water and did not make landfall.")

    # Weakening for major hurricanes
    if target_major and len(obs_list) >= 6:
        # Find the last observation status
        final_statuses = [o["status"] for o in obs_list[-4:]]
        if "TD" in final_statuses or "EX" in final_statuses:
            if "EX" in final_statuses:
                sentences.append("The system eventually weakened and transitioned into an extratropical cyclone.")
            else:
                sentences.append("The storm gradually weakened to a tropical depression before dissipating.")

    # Duration
    if duration_days >= 1:
        days_int = round(duration_days)
        if days_int == 1:
            sentences.append("The system persisted for approximately 1 day.")
        else:
            sentences.append(f"The system persisted for approximately {days_int} days.")
    else:
        sentences.append("The system was short-lived, lasting less than a day.")

    # Notable facts
    notable = []
    if peak_cat == 5:
        notable.append("As a Category 5 hurricane, it was among the most intense Atlantic tropical cyclones on record.")
    if peak_cat == 4 and target_major:
        notable.append("As a Category 4 hurricane, it possessed exceptionally dangerous winds capable of catastrophic damage.")
    if duration_days > 14:
        notable.append(f"Its {round(duration_days)}-day duration made it an exceptionally long-lived system.")
    elif duration_days > 10 and target_major:
        notable.append(f"With a duration of approximately {round(duration_days)} days, it was a notably long-lived storm.")
    if min_pres_val and min_pres_val > 0 and min_pres_val < 920:
        notable.append(f"Its minimum pressure of {min_pres_val} mb was remarkably low, indicating extreme intensity.")
    elif min_pres_val and min_pres_val > 0 and min_pres_val < 940 and target_major:
        notable.append(f"A minimum pressure of {min_pres_val} mb reflected the storm's significant intensity.")

    for n in notable:
        sentences.append(n)

    # Number of observations (for context on data density, only for pre-named era)
    if name == "UNNAMED" and len(obs_list) >= 2:
        sentences.append(f"The storm was tracked across {len(obs_list)} observations in the HURDAT2 database.")

    # Dissipation
    dissipation_area = get_basin_area(last_lat, last_lon)
    if last_date != first_date:
        sentences.append(f"The system dissipated over {dissipation_area} on {format_date_short(last_date)}.")

    narrative = " ".join(sentences)

    # Trim if too long (target: 150-200 for major, 80-120 for others)
    # We don't hard-truncate but the structure above should keep it in range
    return narrative

# ── Main ────────────────────────────────────────────────────────────

def main():
    print("Parsing HURDAT2 raw data...")
    storms = parse_hurdat2(HURDAT2_FILE)
    print(f"  Parsed {len(storms)} storms from HURDAT2")

    print("Reading existing CSV...")
    with open(ALL_CSV, "r") as f:
        reader = csv.DictReader(f)
        original_fields = reader.fieldnames[:]
        rows = list(reader)
    print(f"  Read {len(rows)} rows from CSV")

    # Generate narratives and retired flag
    print("Generating narratives...")
    narr_count = 0
    retired_count = 0
    cat5_count = 0
    major_count = 0

    for row in rows:
        sid = row["storm_id"]
        name = row["name"].strip().upper()

        # Is retired?
        is_retired = 1 if name in RETIRED_NAMES else 0
        row["is_retired"] = is_retired
        if is_retired:
            retired_count += 1

        # Generate narrative
        if sid in storms:
            obs_list = storms[sid]["observations"]
            narrative = generate_narrative(sid, obs_list, row["name"].strip(), row)
            narr_count += 1
        else:
            narrative = f"No detailed track data available for {row['name']} ({sid})."

        row["narrative"] = narrative

        cat_num = int(row["category_num"]) if row["category_num"] else 0
        if cat_num == 5:
            cat5_count += 1
        if cat_num >= 3:
            major_count += 1

    # Write updated all CSV
    output_fields = original_fields + ["narrative", "is_retired"]
    print(f"Writing {ALL_CSV}...")
    with open(ALL_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    # Write 50yr CSV (1976+ hurricanes only)
    print(f"Writing {FIFTY_CSV}...")
    fifty_rows = [r for r in rows if int(r["year"]) >= 1976 and int(r["is_hurricane"]) == 1]
    with open(FIFTY_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(fifty_rows)

    # Summary stats
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total storms processed:    {len(rows)}")
    print(f"Narratives generated:      {narr_count}")
    print(f"Retired names matched:     {retired_count}")
    print(f"Major hurricanes (Cat 3+): {major_count}")
    print(f"Category 5 hurricanes:     {cat5_count}")
    print(f"50-year file rows:         {len(fifty_rows)}")
    print()

    # Show a few sample narratives
    samples = [
        ("Cat 5 example", lambda r: int(r["category_num"]) == 5 if r["category_num"] else False),
        ("Cat 3 example", lambda r: int(r["category_num"]) == 3 if r["category_num"] else False),
        ("TS example", lambda r: r["category"] == "TS"),
        ("Retired name", lambda r: int(r["is_retired"]) == 1),
    ]
    for label, predicate in samples:
        for r in rows:
            try:
                if predicate(r):
                    print(f"\n--- {label}: {r['name']} ({r['storm_id']}, {r['year']}) ---")
                    print(f"Words: {len(r['narrative'].split())}")
                    print(r["narrative"])
                    break
            except (ValueError, KeyError):
                continue

    print("\nDone.")

if __name__ == "__main__":
    main()
