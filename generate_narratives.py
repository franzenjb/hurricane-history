#!/usr/bin/env python3
"""
Generate reporter-style narratives for all 2,004 Atlantic storms from HURDAT2 raw data.
Adds 'narrative' and 'is_retired' columns to the CSV files.

Improvement 1: Varied, engaging prose with dramatic verbs, comparisons, and Notable bullets.
Improvement 2: Curated enrichment dictionary for ~100 historically significant storms.
"""

import csv
import math
import random
import hashlib
from datetime import datetime, timedelta
from collections import OrderedDict

HURDAT2_FILE = "/Users/jefffranzen/hurricane-history/hurdat2-raw.txt"
ALL_CSV = "/Users/jefffranzen/hurricane-history/atlantic_hurricanes_all.csv"
FIFTY_CSV = "/Users/jefffranzen/hurricane-history/atlantic_hurricanes_50yr.csv"

# ── Retired Atlantic hurricane names ──────────────────────────────
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

# ── Saffir-Simpson scale thresholds (knots) ──────────────────────
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

# ── Geography helpers ─────────────────────────────────────────────
def get_basin_area(lat, lon):
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

def get_basin_area_short(lat, lon):
    """Shorter, more evocative basin descriptions for varied openers."""
    if 18 <= lat <= 31 and -98 <= lon <= -82:
        return "the warm waters of the Gulf of Mexico"
    if 9 <= lat <= 22 and -88 <= lon <= -60:
        return "the Caribbean"
    if 8 <= lat <= 25 and -35 <= lon <= -15:
        return "a tropical wave rolling off the African coast"
    if 10 <= lat <= 25 and -65 <= lon <= -35:
        return "the deep tropical Atlantic"
    if 25 <= lat <= 45 and -82 <= lon <= -65:
        return "the western Atlantic"
    if 20 <= lat <= 40 and -82 <= lon <= -65:
        return "subtropical waters"
    return "the open Atlantic"

def get_landfall_area(lat, lon):
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
    if lat >= 40 and -80 <= lon <= -60:
        return "the northeastern U.S."
    if 42 <= lat <= 50 and -70 <= lon <= -55:
        return "Atlantic Canada"
    return get_basin_area(lat, lon)

def compute_direction(lat1, lon1, lat2, lon2):
    if abs(lat2 - lat1) < 1 and abs(lon2 - lon1) < 1:
        return "remained nearly stationary"
    angle = math.degrees(math.atan2(lon2 - lon1, lat2 - lat1))
    if -22.5 <= angle < 22.5: return "tracked northward"
    elif 22.5 <= angle < 67.5: return "tracked northeastward"
    elif 67.5 <= angle < 112.5: return "tracked eastward"
    elif 112.5 <= angle < 157.5: return "tracked southeastward"
    elif angle >= 157.5 or angle < -157.5: return "tracked southward"
    elif -157.5 <= angle < -112.5: return "tracked southwestward"
    elif -112.5 <= angle < -67.5: return "tracked westward"
    elif -67.5 <= angle < -22.5: return "tracked northwestward"
    return "tracked across the basin"

def detect_recurvature(lats, lons):
    if len(lats) < 6: return False
    mid = len(lats) // 2
    first_dlon = lons[mid] - lons[0]
    second_dlon = lons[-1] - lons[mid]
    second_dlat = lats[-1] - lats[mid]
    return first_dlon < -3 and second_dlon > 2 and second_dlat > 2

def format_date(datestr):
    dt = datetime.strptime(datestr, "%Y%m%d")
    return dt.strftime("%B %d, %Y").replace(" 0", " ")

def format_date_short(datestr):
    dt = datetime.strptime(datestr, "%Y%m%d")
    return dt.strftime("%B %d").replace(" 0", " ")

# ── Deterministic pseudo-random selection based on storm ID ───────
def storm_hash(storm_id, salt=""):
    """Return a deterministic int 0-999 for a storm ID + optional salt."""
    h = hashlib.md5((storm_id + salt).encode()).hexdigest()
    return int(h[:8], 16) % 1000

def pick(storm_id, options, salt=""):
    """Deterministically pick from a list based on storm_id."""
    idx = storm_hash(storm_id, salt) % len(options)
    return options[idx]

# ── Dramatic verb/phrase pools ────────────────────────────────────
FORMATION_OPENERS_NAMED_HU = [
    lambda name, area, date, year: f"Hurricane {name} roared to life in {area} on {date}, {year}.",
    lambda name, area, date, year: f"Born from a cluster of thunderstorms over {area}, Hurricane {name} took shape on {date}, {year}.",
    lambda name, area, date, year: f"What began as a disorganized tropical disturbance in {area} on {date}, {year} would soon become Hurricane {name}.",
    lambda name, area, date, year: f"Hurricane {name} emerged from {area} on {date}, {year}, quickly organizing into a formidable cyclone.",
    lambda name, area, date, year: f"On {date}, {year}, a swirl of convection in {area} coalesced into Hurricane {name}.",
    lambda name, area, date, year: f"Hurricane {name} spun up over {area} on {date}, {year}.",
    lambda name, area, date, year: f"The {year} season saw Hurricane {name} materialize over {area} on {date}.",
]

FORMATION_OPENERS_NAMED_TS = [
    lambda name, area, date, year: f"Tropical Storm {name} formed over {area} on {date}, {year}.",
    lambda name, area, date, year: f"A tropical disturbance in {area} organized into Tropical Storm {name} on {date}, {year}.",
    lambda name, area, date, year: f"On {date}, {year}, Tropical Storm {name} developed from a low-pressure system over {area}.",
    lambda name, area, date, year: f"Tropical Storm {name} came together over {area} on {date}, {year}, drawing energy from warm sea-surface temperatures.",
    lambda name, area, date, year: f"The tropical waters of {area} gave rise to Tropical Storm {name} on {date}, {year}.",
]

FORMATION_OPENERS_UNNAMED = [
    lambda sid, area, date, year: f"An unnamed storm ({sid}) formed over {area} on {date}, {year}.",
    lambda sid, area, date, year: f"A tropical system designated {sid} developed over {area} on {date}, {year}.",
    lambda sid, area, date, year: f"On {date}, {year}, a storm tracked as {sid} emerged over {area}.",
    lambda sid, area, date, year: f"The records show a storm ({sid}) developing over {area} on {date}, {year}.",
]

FORMATION_OPENERS_MAJOR = [
    lambda name, area, date, year: f"One of the most powerful storms of the {year} season, Hurricane {name} churned to life over {area} on {date}.",
    lambda name, area, date, year: f"Hurricane {name} exploded onto the scene over {area} on {date}, {year}, destined to become a monster.",
    lambda name, area, date, year: f"What would become a devastating major hurricane first appeared as a tropical disturbance over {area} on {date}, {year} — Hurricane {name} was born.",
    lambda name, area, date, year: f"On {date}, {year}, the {year} hurricane season produced one of its fiercest storms: Hurricane {name} formed over {area}.",
    lambda name, area, date, year: f"Hurricane {name} gathered strength over {area} starting {date}, {year}, rapidly evolving into a fearsome cyclone.",
]

INTENSIFICATION_PHRASES = [
    "rapidly intensified into a {cat}",
    "exploded in intensity, reaching {cat} strength",
    "powered up to {cat} status",
    "strengthened into a ferocious {cat}",
    "muscled its way to {cat} intensity",
]

LANDFALL_VERBS = [
    "slammed into {area}",
    "barreled ashore near {area}",
    "carved a destructive path into {area}",
    "made landfall near {area}",
    "crashed ashore along {area}",
    "struck {area}",
    "hammered {area}",
    "battered {area}",
]

TRACK_PHRASES_RECURVE = [
    "The storm initially churned westward before hooking northeastward across the Atlantic.",
    "After tracking west through the tropics, the system recurved sharply to the northeast.",
    "It carved a classic recurving track — west through the Caribbean, then curling northeastward.",
    "The storm followed the textbook recurvature pattern, sweeping west before arcing into the mid-latitudes.",
]

DISSIPATION_PHRASES = [
    "The storm finally wound down over {area} on {date}.",
    "By {date}, the system had unraveled over {area}.",
    "The remnants fizzled out over {area} by {date}.",
    "It dissipated over {area} on {date}.",
    "The cyclone lost its structure over {area} by {date}.",
]

WEAKENING_ET = [
    "The system eventually lost its tropical characteristics and transitioned into an extratropical cyclone.",
    "As it raced into higher latitudes, the storm shed its tropical identity and became extratropical.",
    "It underwent extratropical transition, merging with the mid-latitude westerlies.",
]

WEAKENING_TD = [
    "The storm gradually weakened to a tropical depression before falling apart.",
    "Sapped of its energy, the system wound down to a tropical depression and dissipated.",
    "Wind shear and cooler waters conspired to weaken the storm to a depression before it died out.",
]

# ── Curated enrichment for ~100 historically significant storms ───
ENRICHMENT = {
    # Pre-1900
    "AL061856": {  # Last Island 1856
        "impact": "The Last Island Hurricane devastated Isle Derniere, Louisiana, killing an estimated 200 people and washing the resort island nearly flat. It was one of the deadliest storms of the pre-Civil War era.",
        "notable": ["Destroyed the resort island of Isle Derniere, Louisiana", "Killed approximately 200 people", "One of the most destructive Gulf storms of the 19th century"]
    },
    "AL031893": {  # Sea Islands 1893
        "impact": "The Sea Islands Hurricane struck South Carolina with catastrophic storm surge, killing between 1,000 and 2,000 people, mostly freed slaves and their descendants on the barrier islands near Beaufort.",
        "notable": ["Killed 1,000-2,000 people in South Carolina's Sea Islands", "One of the deadliest U.S. hurricanes in history", "Devastated African-American communities on coastal barrier islands"]
    },
    "AL061893": {  # Chenier Caminada 1893
        "impact": "The Cheniere Caminada Hurricane obliterated the fishing village of Cheniere Caminada, Louisiana, killing approximately 1,100-1,400 people — nearly half the town's population.",
        "notable": ["Killed 1,100-1,400 people in Louisiana", "Destroyed the village of Cheniere Caminada", "Second deadliest U.S. hurricane at the time"]
    },
    # Galveston 1900
    "AL041900": {
        "impact": "The Galveston Hurricane of 1900 remains the deadliest natural disaster in United States history. The storm's massive surge inundated the island city, killing an estimated 8,000 to 12,000 people. The catastrophe led to construction of the Galveston Seawall and the ambitious grade-raising of the entire city.",
        "notable": ["Deadliest natural disaster in U.S. history with 8,000-12,000 deaths", "15-foot storm surge submerged the entire island of Galveston", "Led to construction of the Galveston Seawall and the Galveston Grade Raising", "Shifted Texas's economic center from Galveston to Houston"]
    },
    # 1909 Grand Isle
    "AL061909": {
        "impact": "The Grand Isle Hurricane struck Louisiana as a Category 4 storm, devastating Grand Isle and surrounding areas. An estimated 350 people perished.",
        "notable": ["Killed approximately 350 people in Louisiana", "Struck Grand Isle as a powerful Category 4 hurricane"]
    },
    # Great Miami 1926
    "AL061926": {
        "impact": "The Great Miami Hurricane slammed into the booming city of Miami as a Category 4 storm, killing at least 372 people and causing catastrophic destruction. Adjusted for inflation and coastal development, it remains one of the costliest U.S. hurricanes ever. The storm effectively ended the Florida land boom of the 1920s.",
        "notable": ["Killed at least 372 people in south Florida and the Gulf states", "Ended the 1920s Florida land boom", "Would be the costliest U.S. hurricane if adjusted for modern development", "Eye passed directly over downtown Miami"]
    },
    # Okeechobee 1928
    "AL041928": {
        "impact": "The Okeechobee Hurricane carved a deadly path from the Caribbean to Florida, killing an estimated 2,500 or more people — most of them migrant farm workers drowned when storm surge breached the earthen dike around Lake Okeechobee. It ranks as the second deadliest natural disaster in U.S. history.",
        "notable": ["Killed 2,500+ people, mostly from the Lake Okeechobee flood", "Second deadliest natural disaster in U.S. history", "Led to federal construction of the Herbert Hoover Dike", "Also devastated Guadeloupe and Puerto Rico with over 1,500 deaths"]
    },
    # San Felipe II / Okeechobee (same storm)

    # 1930 Dominican Republic
    "AL021930": {
        "impact": "The Santo Domingo Hurricane struck the Dominican Republic as a powerful Category 4 storm, killing an estimated 2,000-8,000 people and devastating the capital city.",
        "notable": ["Killed 2,000-8,000 people in the Dominican Republic", "One of the deadliest Caribbean hurricanes of the 20th century"]
    },
    # Cuba 1932
    "AL101932": {
        "impact": "The Cuba Hurricane of 1932 was one of the most intense Atlantic hurricanes ever recorded, striking western Cuba with devastating force. Approximately 3,033 people were killed.",
        "notable": ["Killed over 3,000 people in Cuba", "Minimum pressure of 918 mb, among the lowest recorded at the time", "One of the most intense storms in Atlantic basin history"]
    },
    # Labor Day 1935
    "AL021935": {
        "impact": "The Labor Day Hurricane of 1935 slammed into the Florida Keys with a pressure of 892 mb — the lowest ever recorded for a U.S. landfall at the time (a record that stood until Hurricane Milton in 2024). The Category 5 storm killed 408 people, including 259 World War I veterans working on the Overseas Railroad.",
        "notable": ["892 mb — strongest U.S. landfall pressure until 2024", "Killed 408 people including 259 WWI veterans in the Florida Keys", "Destroyed Henry Flagler's Overseas Railroad", "Winds estimated at 185 mph"]
    },
    # New England 1938
    "AL041938": {
        "impact": "The Great New England Hurricane of 1938 — the 'Long Island Express' — raced northward at nearly 70 mph, slamming Long Island and New England with virtually no warning. The storm killed 682 people, injured 1,754, destroyed over 57,000 homes, and reshaped the New England coastline.",
        "notable": ["Killed 682 people across Long Island and New England", "Forward speed reached nearly 70 mph, among the fastest on record", "Destroyed or damaged over 57,000 homes", "Created new inlets on Long Island and stripped beaches across Rhode Island"]
    },
    # Carol 1954
    "AL091954": {
        "impact": "Hurricane Carol raked the northeastern United States, hitting Long Island and New England with destructive winds and storm surge. The storm killed 72 people and caused roughly $460 million in damage (1954 dollars).",
        "notable": ["Killed 72 people in the northeastern U.S.", "Steeple of Boston's Old North Church toppled by Carol's winds", "Triggered major improvements to hurricane warning systems for New England"]
    },
    # Hazel 1954
    "AL101954": {
        "impact": "Hurricane Hazel struck near the North Carolina/South Carolina border as a Category 4 storm, then raced inland with unusual intensity. The storm killed over 1,000 people in Haiti and 95 in the U.S. and Canada combined, devastating communities from the Carolinas to Toronto.",
        "notable": ["Killed over 1,000 people in Haiti and 95 in the U.S./Canada", "Struck as far north as Toronto, Ontario as a powerful extratropical storm", "Category 4 at North Carolina landfall — one of the strongest to hit that far north", "Destroyed every building on the waterfront at Long Beach, NC"]
    },
    # Diane 1955
    "AL051955": {
        "impact": "Though only a Category 1 hurricane at landfall, Diane produced catastrophic inland flooding across the northeastern United States, killing 184 people. It was the first billion-dollar hurricane in U.S. history.",
        "notable": ["First billion-dollar hurricane in U.S. history", "Killed 184 people, mostly from inland flooding", "Dumped up to 20 inches of rain in New England"]
    },
    # Audrey 1957
    "AL021957": {
        "impact": "Hurricane Audrey struck southwestern Louisiana with a massive storm surge that swept miles inland, killing approximately 416 people — many of whom had ignored evacuation warnings for Cameron Parish.",
        "notable": ["Killed approximately 416 people in southwestern Louisiana", "Storm surge penetrated 20+ miles inland in Cameron Parish", "One of the deadliest U.S. hurricanes of the modern era"]
    },
    # Donna 1960
    "AL051960": {
        "impact": "Hurricane Donna carved a devastating trail across the entire U.S. Eastern Seaboard, striking Florida, the Carolinas, and New England with hurricane-force winds — the only storm on record to produce hurricane-force winds in Florida, the Mid-Atlantic, and New England on a single track.",
        "notable": ["Only hurricane to produce hurricane-force winds in FL, Mid-Atlantic, and New England", "Killed 364 people across the Caribbean and U.S.", "Maximum sustained winds of 185 mph over the open Atlantic", "Struck the Florida Keys, then the Carolinas, then Long Island"]
    },
    # Carla 1961
    "AL121961": {
        "impact": "Hurricane Carla was a massive Category 4 hurricane that battered the Texas coast, prompting the largest peacetime evacuation in U.S. history at the time — over 500,000 people fled. Dan Rather's live television coverage from Galveston launched his career.",
        "notable": ["Prompted evacuation of 500,000+ people — largest in U.S. history at the time", "Dan Rather's live TV coverage launched his career as a national journalist", "Category 4 landfall on the central Texas coast with 145 mph winds"]
    },
    # Hattie 1961
    "AL111961": {
        "impact": "Hurricane Hattie devastated British Honduras (now Belize), destroying Belize City so thoroughly that the capital was relocated inland to Belmopan.",
        "notable": ["Destroyed Belize City, forcing relocation of the capital to Belmopan", "Killed over 300 people in Central America", "Category 5 strength at peak"]
    },
    # Flora 1963
    "AL061963": {
        "impact": "Hurricane Flora stalled over Haiti and Cuba for days, producing catastrophic rainfall and flooding. It killed approximately 7,186 people — making it one of the deadliest Atlantic hurricanes in history.",
        "notable": ["Killed approximately 7,186 people in Haiti and Cuba", "Stalled over eastern Cuba for nearly four days", "One of the deadliest Atlantic hurricanes of the 20th century"]
    },
    # Betsy 1965
    "AL081965": {
        "impact": "Hurricane Betsy — dubbed 'Billion Dollar Betsy' — struck southeastern Louisiana with Category 3 winds and massive storm surge that flooded New Orleans' Lower Ninth Ward. It was the first hurricane to cause over $1 billion in damage.",
        "notable": ["First hurricane to exceed $1 billion in damage", "Storm surge flooded New Orleans' Lower Ninth Ward", "Killed 75 people in the U.S. and the Bahamas", "Led directly to authorization of the Lake Pontchartrain hurricane protection project"]
    },
    # Camille 1969
    "AL091969": {
        "impact": "Hurricane Camille smashed into the Mississippi Gulf Coast as one of only four Category 5 hurricanes to make U.S. landfall, with estimated winds of 175 mph and a devastating storm surge that obliterated entire communities. The storm killed 259 people — 113 from inland flooding in Virginia as its remnants stalled over the Appalachians.",
        "notable": ["Category 5 at landfall with estimated 175 mph winds and 909 mb pressure", "Killed 259 people — 113 from inland flooding in Virginia", "Storm surge estimated at 24 feet along the Mississippi coast", "Pass Christian, Mississippi was virtually wiped off the map"]
    },
    # Agnes 1972
    "AL011972": {
        "impact": "Though only a Category 1 hurricane at landfall in the Florida Panhandle, Agnes produced devastating inland flooding from Virginia to New York as its remnants merged with a mid-latitude low. It killed 122 people and caused $2.1 billion in damage — making it the costliest U.S. hurricane at the time.",
        "notable": ["Killed 122 people, mostly from catastrophic inland flooding", "Costliest U.S. hurricane at the time at $2.1 billion", "Wilkes-Barre, Pennsylvania nearly destroyed by Susquehanna River flooding", "Remains one of the worst flood disasters in U.S. Northeast history"]
    },
    # Fifi 1974
    "AL061974": {
        "impact": "Hurricane Fifi devastated Honduras, killing an estimated 8,000-10,000 people — mostly from massive flooding and mudslides. It remains one of the deadliest Atlantic hurricanes in history.",
        "notable": ["Killed 8,000-10,000 people in Honduras", "Catastrophic flooding and mudslides in Central America", "One of the deadliest Atlantic hurricanes in recorded history"]
    },
    # David 1979
    "AL041979": {
        "impact": "Hurricane David struck the Dominican Republic as a Category 5 hurricane, killing over 2,000 people across the Caribbean. It later made U.S. landfall in Florida as a weakened but still dangerous storm.",
        "notable": ["Killed over 2,000 people, primarily in the Dominican Republic and Dominica", "Category 5 at peak with 175 mph winds", "One of the deadliest Atlantic hurricanes of the 1970s"]
    },
    # Allen 1980
    "AL051980": {
        "impact": "Hurricane Allen was a record-breaking Category 5 monster that terrorized the Caribbean with sustained winds of 190 mph — among the highest ever recorded in the Atlantic. Though it weakened before hitting Texas, its sheer power left a lasting mark on the meteorological record.",
        "notable": ["Peak winds of 190 mph — among the highest ever recorded in the Atlantic", "Reached Category 5 strength three separate times", "Minimum pressure of 899 mb, one of the lowest in Atlantic history", "Traveled across the entire Caribbean basin"]
    },
    # Alicia 1983
    "AL031983": {
        "impact": "Hurricane Alicia struck the Houston-Galveston area as a Category 3 storm, killing 21 people and causing $2.6 billion in damage. Glass from downtown Houston's shattered skyscrapers littered the streets.",
        "notable": ["Killed 21 people and caused $2.6 billion in damage in the Houston area", "Shattered glass from downtown Houston skyscrapers", "First significant hurricane to hit a major U.S. metro area in years"]
    },
    # Gilbert 1988
    "AL121988": {
        "impact": "Hurricane Gilbert was the most intense Atlantic hurricane ever recorded at the time, bottoming out at 888 mb as it devastated Jamaica and the Yucatan Peninsula. The storm killed over 300 people across the Caribbean and Mexico.",
        "notable": ["888 mb — lowest pressure ever recorded in the Atlantic at the time", "Killed over 300 people across Jamaica, Mexico, and Central America", "Devastated Jamaica with 185 mph winds", "Held the Atlantic intensity record for 17 years"]
    },
    # Joan 1988
    "AL141988": {
        "impact": "Hurricane Joan tore through Central America at an unusually low latitude, devastating Nicaragua and killing over 200 people. After crossing into the Pacific, the remnants regenerated as Tropical Storm Miriam.",
        "notable": ["Killed over 200 people in Nicaragua and neighboring countries", "Crossed Central America and regenerated as Tropical Storm Miriam in the Pacific", "Struck at an unusually low latitude for a major hurricane"]
    },
    # Hugo 1989
    "AL081989": {
        "impact": "Hurricane Hugo barreled into Charleston, South Carolina as a powerful Category 4 hurricane with 140 mph winds, devastating the historic city and the surrounding Lowcountry. The storm killed 67 people and caused $10 billion in damage. Hugo also ravaged the U.S. Virgin Islands and Puerto Rico before striking the mainland.",
        "notable": ["Category 4 landfall near Charleston, SC with 140 mph winds", "Killed 67 people and caused $10 billion in damage", "Destroyed 90% of structures on St. Croix, USVI", "Winds gusted to 160+ mph in the Francis Marion National Forest"]
    },
    # Bob 1991
    "AL021991": {
        "impact": "Hurricane Bob raked the northeastern United States from North Carolina to New England, causing significant damage to Long Island, Rhode Island, and Cape Cod. The storm killed 17 people.",
        "notable": ["Killed 17 people across the northeastern U.S.", "Caused significant damage to Cape Cod and the New England coast", "Prompted retirement of the name Bob"]
    },
    # Andrew 1992
    "AL041992": {
        "impact": "Hurricane Andrew obliterated Homestead, Florida as a Category 5 hurricane with 165 mph winds, leaving a 30-mile-wide swath of near-total destruction across southern Miami-Dade County. The storm killed 65 people and caused $27 billion in damage, fundamentally reshaping Florida's building codes and insurance industry.",
        "notable": ["Category 5 landfall in Homestead, FL with 165 mph winds", "Killed 65 people and caused $27 billion in damage", "Destroyed 25,524 homes and damaged 101,241 others in Dade County", "Led to sweeping reforms in Florida building codes and insurance regulation"]
    },
    # Mitch 1998
    "AL131998": {
        "impact": "Hurricane Mitch was one of the deadliest Atlantic hurricanes in history, killing over 11,000 people — primarily in Honduras and Nicaragua — as catastrophic rainfall triggered massive flooding and mudslides that buried entire villages. The storm crippled Central America's infrastructure for years.",
        "notable": ["Killed over 11,000 people — deadliest Atlantic hurricane since 1780", "Stalled near Honduras for days, dumping 3+ feet of rain", "Entire villages buried by mudslides in Honduras and Nicaragua", "Set back Honduras's economic development by decades"]
    },
    # Georges 1998
    "AL071998": {
        "impact": "Hurricane Georges carved a destructive path across the Caribbean from the Lesser Antilles to the Gulf Coast, making seven landfalls and killing over 600 people.",
        "notable": ["Made seven landfalls across the Caribbean and Gulf Coast", "Killed over 600 people, primarily in the Dominican Republic and Haiti", "Caused major damage in Puerto Rico and the U.S. Gulf Coast"]
    },
    # Floyd 1999
    "AL081999": {
        "impact": "Hurricane Floyd triggered the largest peacetime evacuation in U.S. history at the time, with 2.6 million people fleeing the southeastern coast. Though it weakened before landfall, the storm's massive rainfall caused catastrophic flooding across eastern North Carolina, where entire towns were submerged for weeks.",
        "notable": ["Triggered evacuation of 2.6 million people along the U.S. East Coast", "Killed 57 people in the U.S., mostly from inland flooding", "Eastern North Carolina communities submerged for weeks by flooding", "Princeville, NC — oldest town chartered by African Americans — was virtually destroyed"]
    },
    # Lenny 1999
    "AL131999": {
        "impact": "Hurricane Lenny earned the nickname 'Wrong Way Lenny' for its highly unusual west-to-east track through the Caribbean — the opposite of a typical hurricane path.",
        "notable": ["Earned the name 'Wrong Way Lenny' for its east-moving track", "Highly unusual west-to-east path through the Caribbean", "Late-season November hurricane"]
    },
    # Keith 2000
    "AL151200": {
        "impact": "Hurricane Keith stalled over the coast of Belize, dumping enormous rainfall and causing severe flooding. The storm killed 40 people in Central America and Mexico.",
        "notable": ["Stalled over Belize causing catastrophic flooding", "Killed 40 people in Central America and Mexico"]
    },
    # Allison 2001 — technically TS
    "AL012001": {
        "impact": "Though never a hurricane, Tropical Storm Allison produced one of the worst flood disasters in U.S. history, dumping over 35 inches of rain on the Houston metropolitan area. The flooding killed 41 people and caused $9 billion in damage, inundating the Texas Medical Center and thousands of homes.",
        "notable": ["Killed 41 people with $9 billion in damage from catastrophic flooding", "Dumped 35+ inches of rain on Houston over several days", "Inundated the Texas Medical Center, one of the world's largest", "Only tropical storm to have its name retired at the time"]
    },
    # Isabel 2003
    "AL132003": {
        "impact": "Hurricane Isabel struck the Outer Banks of North Carolina as a Category 2 hurricane, carving a new inlet through Hatteras Island and causing widespread damage from the Carolinas to Virginia. Storm surge flooding devastated downtown historic areas of coastal Virginia.",
        "notable": ["Carved a new inlet through Hatteras Island in the Outer Banks", "Killed 51 people across the eastern U.S.", "Storm surge flooded historic areas of Alexandria, VA and Annapolis, MD"]
    },
    # Charley 2004
    "AL032004": {
        "impact": "Hurricane Charley rapidly intensified into a Category 4 hurricane just hours before slamming into Punta Gorda, Florida with 150 mph winds. The compact but ferocious storm killed 10 people and caused $16 billion in damage.",
        "notable": ["Rapidly intensified from Cat 2 to Cat 4 in hours before landfall", "Struck Punta Gorda, FL with 150 mph winds", "First of four hurricanes to strike Florida in the record-breaking 2004 season"]
    },
    # Frances 2004
    "AL062004": {
        "impact": "Hurricane Frances was a massive, slow-moving Category 2 storm that battered Florida for more than 24 hours, affecting nearly the entire state. Its large wind field caused widespread damage from the Bahamas to the Florida Panhandle.",
        "notable": ["Took over 24 hours to cross the Florida peninsula", "One of the largest Atlantic hurricanes on record by wind field", "Second of four hurricanes to strike Florida in 2004"]
    },
    # Ivan 2004
    "AL092004": {
        "impact": "Hurricane Ivan was a long-lived, destructive Category 5 hurricane that terrorized the Caribbean before slamming into Gulf Shores, Alabama as a Category 3 storm. It caused massive damage across the Gulf Coast and spawned 117 tornadoes across the eastern U.S.",
        "notable": ["Reached Category 5 three times during its long life", "Spawned 117 tornadoes across the eastern United States", "Killed 124 people across the Caribbean and United States", "Destroyed the Cayman Islands' infrastructure and devastated Grenada"]
    },
    # Jeanne 2004
    "AL112004": {
        "impact": "Hurricane Jeanne completed the unprecedented 2004 Florida hurricane quartet, striking almost the exact same stretch of coast that Frances had hit just three weeks earlier. The storm killed over 3,000 people in Haiti from catastrophic flooding before reaching Florida.",
        "notable": ["Killed over 3,000 people in Haiti from flooding and mudslides", "Fourth hurricane to strike Florida in the 2004 season", "Struck nearly the same location as Hurricane Frances three weeks earlier"]
    },
    # Dennis 2005
    "AL042005": {
        "impact": "Hurricane Dennis was an early-season major hurricane that struck Cuba twice and made U.S. landfall in the Florida Panhandle as a Category 3 storm, killing 42 people.",
        "notable": ["Struck Cuba as a Category 4 hurricane — twice", "Earliest Category 4 hurricane in the Atlantic at the time", "Preceded Katrina by less than two months"]
    },
    # Katrina 2005
    "AL122005": {
        "impact": "Hurricane Katrina was the costliest and one of the deadliest hurricanes in U.S. history. After striking southern Florida as a Category 1 storm, Katrina exploded over the warm Gulf waters to Category 5 before making devastating landfall near Buras, Louisiana. The failure of New Orleans' federally built levee system led to catastrophic flooding of 80% of the city. The storm killed 1,836 people and caused $125 billion in damage, exposing deep failures in emergency preparedness at every level of government.",
        "notable": ["Killed 1,836 people — one of the deadliest U.S. hurricanes in history", "$125 billion in damage — costliest U.S. hurricane at the time", "Breached 50+ sections of New Orleans' levee system, flooding 80% of the city", "Displaced over 1 million Gulf Coast residents", "Storm surge reached 28 feet along the Mississippi coast"]
    },
    # Rita 2005
    "AL182005": {
        "impact": "Hurricane Rita rapidly intensified to Category 5 with the fourth-lowest pressure ever recorded in the Atlantic at the time (895 mb), triggering a chaotic evacuation of 2.5 million Houston-area residents. Rita struck the Texas-Louisiana border as a Category 3 storm, devastating Cameron Parish, Louisiana.",
        "notable": ["Reached 895 mb — fourth-lowest Atlantic pressure at the time", "Triggered chaotic evacuation of 2.5 million people from Houston", "Devastated Cameron Parish, Louisiana", "100+ evacuees died in the evacuation itself, including a bus fire"]
    },
    # Stan 2005
    "AL202005": {
        "impact": "Though only a Category 1 hurricane, Tropical Storm and Hurricane Stan triggered catastrophic flooding and mudslides across Central America and southern Mexico, killing over 1,600 people — most in Guatemala.",
        "notable": ["Killed over 1,600 people in Central America, mostly Guatemala", "Massive mudslides buried villages in the Guatemalan highlands", "Overshadowed by Katrina and Rita in the same season"]
    },
    # Wilma 2005
    "AL252005": {
        "impact": "Hurricane Wilma set the all-time record for the lowest barometric pressure in the Atlantic basin — an astonishing 882 mb — as it rapidly intensified in the Caribbean. The storm devastated the Yucatan Peninsula before crossing Florida, causing $29 billion in damage.",
        "notable": ["882 mb — lowest pressure EVER recorded in the Atlantic basin", "Underwent the most rapid intensification in Atlantic history at the time", "Devastated Cancun and the Yucatan Peninsula", "Crossed Florida from west to east, causing $29 billion in damage"]
    },
    # Dean 2007
    "AL042007": {
        "impact": "Hurricane Dean was a powerful Category 5 hurricane that struck the Yucatan Peninsula with 175 mph winds — the strongest Atlantic landfall since Andrew in 1992. It tore across the Caribbean, devastating several islands before its Mexican landfall.",
        "notable": ["Category 5 landfall on the Yucatan with 175 mph winds", "Strongest Atlantic hurricane landfall since Andrew (1992)", "Crossed the Caribbean on a near-straight westward track"]
    },
    # Felix 2007
    "AL062007": {
        "impact": "Hurricane Felix rapidly intensified from a tropical storm to a Category 5 hurricane in just over two days, then struck Nicaragua's Mosquito Coast with 160 mph winds. The storm killed over 130 people in Central America.",
        "notable": ["Rapidly intensified from TS to Cat 5 in approximately 51 hours", "Struck Nicaragua as a Category 5 hurricane", "Second Category 5 Atlantic landfall in the same season as Dean"]
    },
    # Gustav 2008
    "AL072008": {
        "impact": "Hurricane Gustav killed over 150 people across the Caribbean before striking Louisiana, triggering the largest evacuation in Louisiana history — 1.9 million people fled ahead of landfall near Cocodrie.",
        "notable": ["Triggered evacuation of 1.9 million people from Louisiana", "Killed over 150 people across the Caribbean", "Struck Louisiana almost exactly three years after Katrina"]
    },
    # Ike 2008
    "AL092008": {
        "impact": "Hurricane Ike was an enormous storm that generated a massive, devastating storm surge across the upper Texas coast. Despite making landfall as 'only' a Category 2 hurricane at Galveston, Ike's sheer size produced surge levels typical of a Category 4 or 5, devastating the Bolivar Peninsula and causing $30 billion in damage.",
        "notable": ["Killed 195 people across the Caribbean and United States", "$30 billion in damage — one of the costliest U.S. hurricanes", "Storm surge completely overwashed the Bolivar Peninsula", "Enormous wind field — tropical storm force winds extended 275 miles from center"]
    },
    # Irene 2011
    "AL092011": {
        "impact": "Hurricane Irene affected the entire U.S. East Coast from North Carolina to New England, killing 49 people — mostly from inland flooding in Vermont, where rivers swelled to levels not seen since 1927.",
        "notable": ["Killed 49 people across the eastern U.S.", "Vermont suffered its worst flooding since 1927", "Affected every state from North Carolina to Maine"]
    },
    # Sandy 2012
    "AL182012": {
        "impact": "Superstorm Sandy merged with a powerful nor'easter to become an unprecedented hybrid storm that devastated the New Jersey and New York coastlines with a record storm surge. The massive cyclone — nearly 1,000 miles across — killed 233 people and caused $70 billion in damage. Sandy's 13-foot surge flooded lower Manhattan, shutting down the New York subway system and plunging much of the city into darkness.",
        "notable": ["Killed 233 people and caused $70 billion in damage", "Record 13-foot storm surge flooded lower Manhattan and the NYC subway", "Largest Atlantic hurricane on record by diameter (~1,000 miles)", "Merged with a winter storm to create an unprecedented hybrid 'Superstorm'", "Destroyed or damaged 650,000 homes along the Jersey Shore and beyond"]
    },
    # Joaquin 2015
    "AL112015": {
        "impact": "Hurricane Joaquin intensified into a powerful Category 4 hurricane that devastated the Bahamas, particularly the islands of Crooked Island and Acklins. The storm was also linked to catastrophic inland flooding in South Carolina, and the cargo ship El Faro sank during the storm with the loss of all 33 crew.",
        "notable": ["Sinking of cargo ship El Faro with loss of all 33 crew", "Devastated the central and southern Bahamas", "Associated with catastrophic South Carolina flooding"]
    },
    # Matthew 2016
    "AL142016": {
        "impact": "Hurricane Matthew was a devastating Category 5 hurricane that killed over 1,600 people — the vast majority in Haiti, where catastrophic flooding and mudslides ravaged a nation still recovering from the 2010 earthquake. Matthew later struck the U.S. Southeast, causing major flooding in North Carolina.",
        "notable": ["Killed over 1,600 people, primarily in Haiti", "Strongest Atlantic hurricane since Felix in 2007", "Devastated Haiti, which was still recovering from the 2010 earthquake", "Caused severe flooding in eastern North Carolina"]
    },
    # Harvey 2017
    "AL092017": {
        "impact": "Hurricane Harvey stalled over southeastern Texas for days after making landfall as a Category 4 hurricane near Rockport, dumping a U.S. record 60.58 inches of rain near Nederland, Texas. The resulting catastrophic flooding submerged vast portions of the Houston metropolitan area, displacing over 30,000 people and damaging or destroying 203,000 homes. Harvey tied with Katrina as the costliest U.S. hurricane at $125 billion.",
        "notable": ["60.58 inches of rain — wettest tropical cyclone in U.S. history", "$125 billion in damage — tied with Katrina as costliest U.S. hurricane", "Over 30,000 people displaced and 203,000 homes damaged or destroyed", "Category 4 landfall near Rockport, TX with 130 mph winds", "Stalled over Texas for four days, causing unprecedented flooding"]
    },
    # Irma 2017
    "AL112017": {
        "impact": "Hurricane Irma maintained 185 mph winds for 37 consecutive hours — the longest any cyclone on Earth has sustained that intensity. The Category 5 monster devastated Barbuda, St. Martin, and the Virgin Islands before raking the Florida Keys and Florida's Gulf Coast, killing 134 people and causing $50 billion in damage.",
        "notable": ["185 mph winds sustained for 37 hours — longest-duration Cat 5 winds on record", "Killed 134 people and caused $50 billion in damage", "Barbuda rendered 'barely habitable' — 95% of structures damaged", "Entire Florida Keys evacuation of 75,000 people", "One of the most powerful Atlantic hurricanes ever recorded"]
    },
    # Maria 2017
    "AL152017": {
        "impact": "Hurricane Maria made a devastating Category 5 landfall on Dominica before striking Puerto Rico as a high-end Category 4, destroying the island's power grid and causing a humanitarian crisis that lasted months. The official death toll was revised to 2,975 — making Maria one of the deadliest U.S.-related disasters in modern history.",
        "notable": ["2,975 deaths in Puerto Rico — deadliest U.S.-related disaster in a century", "Destroyed 100% of Puerto Rico's electrical grid", "Category 5 landfall on Dominica left 90% of structures damaged", "Puerto Rico remained largely without power for months", "Caused $90 billion in damage"]
    },
    # Nate 2017
    "AL162017": {
        "impact": "Hurricane Nate struck Central America with heavy rains before making landfall near Biloxi, Mississippi as a Category 1 hurricane. The storm killed 48 people, primarily in Costa Rica and Nicaragua.",
        "notable": ["Killed 48 people in Central America", "Fastest-moving hurricane in the Gulf of Mexico in years"]
    },
    # Florence 2018
    "AL062018": {
        "impact": "Hurricane Florence stalled near the North Carolina coast, dumping over 30 inches of rain and causing catastrophic, record-breaking flooding across the Carolinas. Rivers crested at all-time highs weeks after landfall, devastating entire communities.",
        "notable": ["Killed 53 people, mostly from inland flooding", "Dumped 30+ inches of rain on parts of North Carolina", "Rivers crested at record levels weeks after the storm passed", "Stalled near the coast, maximizing rainfall totals"]
    },
    # Michael 2018
    "AL142018": {
        "impact": "Hurricane Michael exploded into a Category 5 hurricane just before obliterating Mexico Beach, Florida with 160 mph winds — making it the strongest hurricane to strike the Florida Panhandle on record and only the fourth Category 5 to make U.S. landfall. The storm flattened entire blocks and killed 74 people.",
        "notable": ["Category 5 landfall at Mexico Beach, FL with 160 mph winds", "Strongest hurricane to ever strike the Florida Panhandle", "Fourth Category 5 U.S. landfall in recorded history", "Mexico Beach was virtually leveled by the storm surge and wind", "Killed 74 people and caused $25 billion in damage"]
    },
    # Dorian 2019
    "AL052019": {
        "impact": "Hurricane Dorian reached Category 5 intensity with 185 mph winds and a pressure of 910 mb, then stalled over Great Abaco and Grand Bahama in the Bahamas for nearly two days — an agonizing, historic catastrophe. The storm killed at least 70 people (with hundreds still missing) and destroyed or severely damaged 13,000 homes.",
        "notable": ["185 mph winds tied for strongest Atlantic landfall on record", "Stalled over the Bahamas for nearly 48 hours at Cat 5 intensity", "At least 70 killed in the Bahamas with hundreds unaccounted for", "Entire neighborhoods in Marsh Harbour, Abaco swept away", "Caused over $3.4 billion in damage to the Bahamas"]
    },
    # Laura 2020
    "AL132020": {
        "impact": "Hurricane Laura rapidly intensified into a Category 4 hurricane before slamming into Cameron, Louisiana with 150 mph winds — the strongest storm to strike the state since 1856. Laura killed 77 people and caused $19 billion in damage.",
        "notable": ["Category 4 landfall with 150 mph winds — strongest Louisiana landfall since 1856", "Killed 77 people and caused $19 billion in damage", "Destroyed much of the town of Cameron, Louisiana", "Rapidly intensified over the Gulf of Mexico"]
    },
    # Eta 2020
    "AL292020": {
        "impact": "Hurricane Eta struck Nicaragua as a Category 4 hurricane, then looped through the Caribbean and Gulf of Mexico, making multiple landfalls including two in Florida. Catastrophic flooding across Central America killed over 200 people.",
        "notable": ["Killed over 200 people from flooding in Central America", "Made multiple landfalls including Nicaragua and Florida", "Took a bizarre looping track through the western Caribbean"]
    },
    # Iota 2020
    "AL312020": {
        "impact": "Hurricane Iota became the first Category 5 hurricane in November on record in the Atlantic, then struck Nicaragua — devastatingly close to where Eta had hit just two weeks earlier. The back-to-back strikes compounded an already catastrophic humanitarian crisis.",
        "notable": ["First Category 5 November hurricane in the Atlantic on record", "Struck Nicaragua only 15 miles from where Eta hit two weeks prior", "30th named storm of the record-breaking 2020 season", "Completely destroyed Providencia Island, Colombia"]
    },
    # Ida 2021
    "AL092021": {
        "impact": "Hurricane Ida slammed into Port Fourchon, Louisiana on the 16th anniversary of Katrina as a powerful Category 4 hurricane with 150 mph winds. The storm knocked out power to all of New Orleans and caused $75 billion in damage. Ida's remnants then triggered catastrophic flash flooding in the northeastern U.S., killing 91 people from Louisiana to New York.",
        "notable": ["Category 4 landfall with 150 mph winds — tied for strongest Louisiana landfall", "Knocked out power to all of New Orleans and surrounding parishes", "Remnants caused deadly flash flooding from Pennsylvania to New York", "Killed 91 people total — 33 from flooding in the northeastern U.S.", "$75 billion in total damage"]
    },
    # Fiona 2022
    "AL072022": {
        "impact": "Hurricane Fiona struck Puerto Rico as a Category 1 hurricane, triggering island-wide power outages and catastrophic flooding that devastated communities still recovering from Hurricane Maria five years earlier. Fiona later became the strongest storm to ever strike Atlantic Canada.",
        "notable": ["Caused island-wide blackout in Puerto Rico — still recovering from Maria", "Strongest hurricane ever to strike Atlantic Canada", "Washed homes into the sea in Newfoundland and Nova Scotia"]
    },
    # Ian 2022
    "AL092022": {
        "impact": "Hurricane Ian made a devastating Category 4 landfall on Florida's Gulf Coast near Fort Myers with 150 mph winds, generating catastrophic storm surge that inundated Fort Myers Beach, Sanibel Island, and Pine Island. The storm killed 161 people and caused $110 billion in damage — the third costliest U.S. hurricane on record.",
        "notable": ["Category 4 landfall near Fort Myers, FL with 150 mph winds", "Killed 161 people — deadliest Florida hurricane since 1935", "$110 billion in damage — third costliest U.S. hurricane", "Storm surge of 12-18 feet destroyed Fort Myers Beach and Sanibel Island", "Causeway to Pine Island destroyed, isolating the community for days"]
    },
    # Otis 2023
    "AL182023": {
        "impact": "Hurricane Otis shocked forecasters with the most extreme rapid intensification ever observed in the Eastern Pacific (classified under Atlantic tracking), exploding from a tropical storm to a Category 5 hurricane in just 12 hours before devastating Acapulco, Mexico with 165 mph winds.",
        "notable": ["Most extreme rapid intensification ever recorded in the Eastern Pacific", "Intensified from tropical storm to Category 5 in 12 hours", "Devastated Acapulco, Mexico with 165 mph winds", "Killed at least 52 people"]
    },
    # Beryl 2024
    "AL022024": {
        "impact": "Hurricane Beryl became the earliest Category 5 hurricane in Atlantic history, reaching that intensity on July 2, 2024. Beryl devastated the Windward Islands, struck Jamaica and the Yucatan, then made landfall in Texas.",
        "notable": ["Earliest Category 5 hurricane in Atlantic recorded history (July 2)", "Devastated Carriacou, Grenada and the Windward Islands", "Made landfall in Texas as a Category 1 after crossing the Caribbean"]
    },
    # Milton 2024
    "AL142024": {
        "impact": "Hurricane Milton underwent the fastest rapid intensification ever recorded in the Atlantic basin, exploding from a Category 1 to a Category 5 hurricane in less than 24 hours with a minimum pressure of 897 mb. Milton struck Florida's Gulf Coast near Siesta Key, generating deadly tornadoes across the peninsula and a destructive storm surge, killing at least 36 people.",
        "notable": ["Fastest rapid intensification in Atlantic history — Cat 1 to Cat 5 in under 24 hours", "897 mb — fifth-lowest pressure in Atlantic history", "Generated deadly tornado outbreak across Florida", "Struck Florida just two weeks after Hurricane Helene", "Broke the record for lowest pressure in the Gulf of Mexico"]
    },
    # Helene 2024
    "AL092024": {
        "impact": "Hurricane Helene made a large Category 4 landfall in Florida's Big Bend region, then maintained unusual intensity far inland as its remnants devastated the southern Appalachians with catastrophic flooding. Western North Carolina and eastern Tennessee experienced once-in-a-thousand-year rainfall, with Asheville and surrounding communities suffering apocalyptic destruction.",
        "notable": ["Killed over 230 people — deadliest mainland U.S. hurricane since Katrina", "Catastrophic flooding devastated Asheville, NC and the southern Appalachians", "Category 4 landfall in Florida's Big Bend with 140 mph winds", "Storm surge of 15+ feet in parts of Florida's Gulf Coast", "Over $50 billion in damage across multiple states"]
    },
    # Additional historical storms
    "AL031932": {  # Bahamas 1932
        "impact": "A devastating Category 5 hurricane struck the Bahamas with extreme force, killing 16 people on the islands.",
        "notable": ["Reached Category 5 intensity", "One of the most intense hurricanes of the 1930s"]
    },
    "AL101933": {  # Cuba-Brownsville 1933
        "impact": "The Cuba-Brownsville Hurricane struck southern Texas and northern Mexico, killing 40 people in the U.S. and approximately 67 in Mexico.",
        "notable": ["Category 3 at Texas landfall", "Part of the hyperactive 1933 hurricane season — the most active on record at the time"]
    },
    "AL151933": {  # Tampico 1933
        "impact": "The Tampico Hurricane struck northeastern Mexico as a powerful Category 5 storm, killing approximately 184 people and devastating the city of Tampico.",
        "notable": ["Category 5 at landfall in Mexico", "Killed approximately 184 people", "One of the most intense Pacific-side landfalls of the era"]
    },
    "AL011944": {  # Great Atlantic 1944
        "impact": "The Great Atlantic Hurricane struck the North Carolina Outer Banks, then barreled up the coast into New England, sinking numerous ships and killing 390 people — including 344 aboard ships at sea.",
        "notable": ["Killed 390 people, 344 of them at sea", "Sank or damaged numerous U.S. Navy vessels and merchant ships", "One of the most destructive wartime hurricanes"]
    },
    "AL091947": {  # Fort Lauderdale 1947
        "impact": "The Fort Lauderdale Hurricane struck southeastern Florida as a Category 4 storm, then crossed the state and hit the Gulf Coast again near New Orleans, killing 51 people.",
        "notable": ["Struck Florida as a Category 4, then hit the Gulf Coast again", "Killed 51 people across Florida and the Gulf states"]
    },
    "AL091955": {  # Janet 1955
        "impact": "Hurricane Janet was a catastrophic Category 5 hurricane that destroyed Chetumal, Mexico and killed over 1,000 people across the Caribbean and Central America. A U.S. Navy hurricane hunter aircraft with 11 crew was lost while flying into the storm.",
        "notable": ["Killed over 1,000 people across the Caribbean", "U.S. Navy hurricane hunter aircraft lost in the storm with 11 crew", "Destroyed the city of Chetumal, Mexico"]
    },
    "AL091961": {  # Esther 1961
        "impact": "Hurricane Esther threatened the northeastern United States before recurving, prompting one of the first attempts at hurricane modification through Project Stormfury.",
        "notable": ["Subject of early Project Stormfury cloud-seeding experiments", "Threatened New England before recurving out to sea"]
    },
    "AL091965": {  # Carol — actually Betsy year, but let's add Cleo 1964
    },
    "AL112005": {  # Ophelia 2005
        "impact": "Hurricane Ophelia was an erratic storm that meandered off the southeastern U.S. coast for weeks, bringing tropical storm conditions to North Carolina's Outer Banks.",
        "notable": ["Wandered erratically off the U.S. coast for over two weeks", "One of the slowest-moving storms of the 2005 season"]
    },
    "AL012004": {  # Alex 2004
        "impact": "Hurricane Alex became one of the rare hurricanes to strengthen in the cool waters off the Outer Banks of North Carolina, briefly reaching Category 3 intensity.",
        "notable": ["Rare case of intensification in cool Atlantic waters near the Outer Banks", "Started the hyperactive 2004 hurricane season"]
    },
    # Emily 2005
    "AL052005": {
        "impact": "Hurricane Emily became the earliest Category 5 hurricane in Atlantic history at the time, striking the Yucatan Peninsula and then northeastern Mexico. Emily killed 17 people.",
        "notable": ["Earliest Category 5 on record at the time (July)", "Struck the Yucatan Peninsula and northeastern Mexico", "Record broken by Beryl in 2024"]
    },
    # Opal 1995
    "AL171995": {
        "impact": "Hurricane Opal rapidly intensified to a Category 4 hurricane in the Gulf of Mexico before striking the Florida Panhandle, causing $3 billion in damage. Its rapid intensification caught forecasters off guard.",
        "notable": ["Rapidly intensified to Category 4 in the Gulf of Mexico", "Struck the Florida Panhandle with massive storm surge", "Caused $3 billion in damage"]
    },
    # Luis 1995
    "AL131995": {
        "impact": "Hurricane Luis was a powerful Category 4 hurricane that devastated the northern Leeward Islands, particularly St. Martin and St. Barthelemy, killing 19 people.",
        "notable": ["Devastated St. Martin and neighboring islands", "Category 4 intensity maintained for several days", "Generated massive ocean swells across the Atlantic"]
    },
    # Fran 1996
    "AL061996": {
        "impact": "Hurricane Fran struck the North Carolina coast near Cape Fear as a Category 3 hurricane, then drove inland with destructive winds and flooding that devastated Raleigh and the state's interior. The storm killed 26 people.",
        "notable": ["Category 3 landfall near Cape Fear, NC", "Caused extensive damage far inland in Raleigh and central North Carolina", "Killed 26 people and caused $3.2 billion in damage"]
    },
    # Gloria 1985
    "AL091985": {
        "impact": "Hurricane Gloria, once feared as a potential catastrophic strike, raked the Mid-Atlantic and New England as a weakening hurricane. Though damage was less severe than feared, the storm killed 14 people.",
        "notable": ["First significant hurricane to strike New England since 1960", "Weakened before landfall, sparing the worst-case scenario", "Killed 14 people along the U.S. East Coast"]
    },
    # Elena 1985
    "AL051985": {
        "impact": "Hurricane Elena executed an unusual loop in the Gulf of Mexico, hovering offshore for days while Gulf Coast communities evacuated, before finally striking Mississippi. The storm forced the evacuation of over 1 million people.",
        "notable": ["Executed a rare loop in the Gulf of Mexico", "Forced evacuation of over 1 million Gulf Coast residents", "Hovered offshore for days, testing nerves across the region"]
    },
    # Juan 1985
    "AL121985": {
        "impact": "Hurricane Juan caused devastating flooding across Louisiana, killing 63 people. The slow-moving storm stalled over the Gulf and dumped enormous rainfall inland.",
        "notable": ["Killed 63 people, mostly from flooding in Louisiana", "Slow-moving storm that stalled and dumped torrential rainfall"]
    },
    # Frederic 1979
    "AL061979": {
        "impact": "Hurricane Frederic struck Mobile, Alabama and the Gulf Coast as a major Category 3 hurricane, causing $2.3 billion in damage and killing 5 people in the United States.",
        "notable": ["Category 3 landfall near Mobile, Alabama", "Caused $2.3 billion in damage — expensive for the era", "Devastated Dauphin Island and Gulf Shores"]
    },
    # Celia 1970
    "AL031970": {
        "impact": "Hurricane Celia struck Corpus Christi, Texas as a Category 3 hurricane with incredibly destructive winds, killing 28 people and devastating the city.",
        "notable": ["Destroyed or damaged 90% of buildings in downtown Corpus Christi", "Killed 28 people and caused $930 million in damage", "Extreme wind gusts exceeded 160 mph"]
    },
    # Inez 1966
    "AL101966": {
        "impact": "Hurricane Inez was a compact but violent Category 5 hurricane that struck the Caribbean, killing over 1,000 people — mostly in Haiti. It later weakened and struck Mexico.",
        "notable": ["Killed over 1,000 people, primarily in Haiti and the Dominican Republic", "Reached Category 5 intensity over the Caribbean", "Made multiple landfalls across the Caribbean basin"]
    },
    # Hilda 1964
    "AL091964": {
        "impact": "Hurricane Hilda struck Louisiana as a Category 3 hurricane, killing 38 people. The storm spawned a tornado in Larose, Louisiana that killed 22 people.",
        "notable": ["Killed 38 people in Louisiana", "Spawned a deadly tornado in Larose, Louisiana that killed 22", "Category 3 landfall on the Louisiana coast"]
    },
    # Beulah 1967
    "AL081967": {
        "impact": "Hurricane Beulah struck southern Texas as a Category 3 hurricane, spawning a record 115 tornadoes — the most ever spawned by a tropical cyclone at the time. The storm caused massive flooding along the Rio Grande.",
        "notable": ["Spawned 115 tornadoes — a record for a tropical cyclone at the time", "Category 3 landfall in southern Texas", "Caused massive Rio Grande flooding"]
    },
    # Eloise 1975
    "AL081975": {
        "impact": "Hurricane Eloise struck the Florida Panhandle near Fort Walton Beach as a Category 3 hurricane, generating a powerful storm surge that destroyed beachfront properties along the Emerald Coast.",
        "notable": ["Category 3 landfall on the Florida Panhandle", "Devastating storm surge destroyed beachfront properties", "Killed 80 people across the Caribbean and United States"]
    },
    # Gordon 1994
    "AL081994": {
        "impact": "Though never stronger than a tropical storm in the Atlantic, Gordon killed over 1,100 people in Haiti through catastrophic flooding and mudslides as it wandered erratically through the Caribbean.",
        "notable": ["Killed over 1,100 people in Haiti", "Took a bizarre, looping track through the Caribbean and Gulf", "Demonstrates that weak storms can be the deadliest"]
    },
    # Isidore 2002
    "AL092002": {
        "impact": "Hurricane Isidore stalled over the Yucatan Peninsula for nearly 24 hours before entering the Gulf of Mexico and striking Louisiana as a tropical storm, dumping enormous rainfall.",
        "notable": ["Stalled over the Yucatan for nearly a full day", "Dumped heavy rainfall across Louisiana and the Gulf Coast"]
    },
    # Lili 2002
    "AL132002": {
        "impact": "Hurricane Lili rapidly weakened from a Category 4 to a Category 1 hurricane in just hours before striking Louisiana — one of the most dramatic pre-landfall weakenings on record.",
        "notable": ["Weakened from Category 4 to Category 1 in just hours before landfall", "One of the most dramatic pre-landfall weakenings ever observed"]
    },
    # Noel 2007
    "AL162007": {
        "impact": "Tropical Storm Noel killed over 160 people in the Dominican Republic and Haiti through catastrophic flooding and mudslides.",
        "notable": ["Killed over 160 people in the Caribbean", "Caused catastrophic flooding in the Dominican Republic and Haiti"]
    },
    # Paloma 2008
    "AL172008": {
        "impact": "Hurricane Paloma became the strongest November hurricane on record in the Atlantic at the time, reaching Category 4 before striking Cuba.",
        "notable": ["Strongest November Atlantic hurricane on record at the time", "Category 4 at peak intensity"]
    },
}

# ── Parse HURDAT2 ─────────────────────────────────────────────────

def parse_hurdat2(filepath):
    storms = OrderedDict()
    current_id = None

    with open(filepath, "r") as f:
        for line in f:
            line = line.rstrip()
            parts = [p.strip() for p in line.split(",")]

            if len(parts) >= 3 and parts[0].startswith("AL"):
                candidate_id = parts[0]
                if len(candidate_id) == 8 and candidate_id[2:4].isdigit():
                    current_id = candidate_id
                    storms[current_id] = {
                        "name": parts[1].strip(),
                        "observations": []
                    }
                    continue

            if current_id and len(parts) >= 8:
                lat_str = parts[4].strip()
                lat = float(lat_str[:-1])
                if lat_str.endswith("S"): lat = -lat

                lon_str = parts[5].strip()
                lon = float(lon_str[:-1])
                if lon_str.endswith("W"): lon = -lon

                wind = int(parts[6].strip()) if parts[6].strip() not in ("-999", "") else -999
                pressure = int(parts[7].strip()) if parts[7].strip() not in ("-999", "") else -999

                storms[current_id]["observations"].append({
                    "date": parts[0].strip(),
                    "time": parts[1].strip(),
                    "record_id": parts[2].strip(),
                    "status": parts[3].strip(),
                    "lat": lat, "lon": lon,
                    "wind": wind, "pressure": pressure,
                })

    return storms

# ── Narrative generation ──────────────────────────────────────────

def generate_narrative(storm_id, obs_list, name, csv_row):
    """Generate a reporter-style narrative for one storm."""

    if not obs_list:
        return "No detailed track data available for this storm."

    year = csv_row["year"]
    cat_num = int(csv_row["category_num"]) if csv_row["category_num"] else 0
    max_wind_kt = int(csv_row["max_wind_kt"]) if csv_row["max_wind_kt"] else 0
    is_major = int(csv_row["is_major"]) if csv_row["is_major"] else 0
    is_hurricane = int(csv_row["is_hurricane"]) if csv_row["is_hurricane"] else 0
    num_landfalls = int(csv_row["landfalls"]) if csv_row["landfalls"] else 0
    duration_hours = int(csv_row["duration_hours"]) if csv_row["duration_hours"] else 0
    min_pressure = csv_row.get("min_pressure_mb", "")
    month_num = int(csv_row["month"]) if csv_row["month"] else 0

    # Derived from observations
    lats = [o["lat"] for o in obs_list]
    lons = [o["lon"] for o in obs_list]
    winds = [o["wind"] for o in obs_list if o["wind"] > 0]
    pressures = [o["pressure"] for o in obs_list if o["pressure"] > 0]

    first_lat, first_lon = lats[0], lons[0]
    last_lat, last_lon = lats[-1], lons[-1]
    first_date = obs_list[0]["date"]
    last_date = obs_list[-1]["date"]

    peak_obs = max(obs_list, key=lambda o: o["wind"] if o["wind"] > 0 else 0)
    peak_date = peak_obs["date"]
    peak_wind = peak_obs["wind"]
    peak_cat = saffir_simpson(peak_wind) if peak_wind > 0 else cat_num

    landfall_obs = [o for o in obs_list if o["record_id"] == "L"]
    duration_days = duration_hours / 24.0 if duration_hours else len(obs_list) * 6 / 24.0

    min_pres_val = min(pressures) if pressures else None
    if not min_pres_val and min_pressure and min_pressure not in ("", "-999"):
        try: min_pres_val = int(min_pressure)
        except ValueError: min_pres_val = None

    recurved = detect_recurvature(lats, lons)

    # Rapid intensification check (>=30kt in 24h = 4 observations at 6hr intervals)
    rapid_intensification = False
    ri_amount = 0
    if len(obs_list) >= 4:
        for i in range(len(obs_list) - 4):
            w0 = obs_list[i]["wind"]
            w1 = obs_list[i + 4]["wind"]
            if w0 > 0 and w1 > 0 and (w1 - w0) >= 30:
                rapid_intensification = True
                ri_amount = max(ri_amount, w1 - w0)

    # Areas traversed
    areas_visited = []
    prev_area = None
    for o in obs_list:
        area = get_basin_area(o["lat"], o["lon"])
        if area != prev_area:
            areas_visited.append(area)
            prev_area = area

    lat_range = max(lats) - min(lats)

    # Season context
    season_note = ""
    if month_num in (1, 2, 3, 4, 5):
        season_note = "off-season"
    elif month_num == 6:
        season_note = "early-season"
    elif month_num in (11, 12):
        season_note = "late-season"

    is_named = (name != "UNNAMED")
    title_name = name.title() if is_named else None

    sentences = []

    # ── OPENER (varied by storm type) ─────────────────────────
    formation_area = get_basin_area_short(first_lat, first_lon)
    date_str = format_date_short(first_date)

    if not is_named:
        opener = pick(storm_id, FORMATION_OPENERS_UNNAMED, "opener")
        sentences.append(opener(storm_id, formation_area, date_str, year))
    elif cat_num >= 3:
        opener = pick(storm_id, FORMATION_OPENERS_MAJOR, "opener")
        sentences.append(opener(title_name, formation_area, date_str, year))
    elif is_hurricane:
        opener = pick(storm_id, FORMATION_OPENERS_NAMED_HU, "opener")
        sentences.append(opener(title_name, formation_area, date_str, year))
    else:
        opener = pick(storm_id, FORMATION_OPENERS_NAMED_TS, "opener")
        sentences.append(opener(title_name, formation_area, date_str, year))

    # Season context addendum
    if season_note:
        adj = {"off-season": "an unusual off-season system", "early-season": "an early-season system", "late-season": "a late-season entry"}[season_note]
        sentences.append(f"It was {adj}.")

    # ── TRACK ─────────────────────────────────────────────────
    if recurved:
        sentences.append(pick(storm_id, TRACK_PHRASES_RECURVE, "track"))
    else:
        direction = compute_direction(first_lat, first_lon, last_lat, last_lon)
        if direction == "remained nearly stationary":
            sentences.append("The system remained nearly stationary throughout its brief existence.")
        else:
            verbs = [
                f"The system {direction} during its lifetime.",
                f"It {direction} across the basin.",
                f"The cyclone {direction} over the course of its life.",
            ]
            sentences.append(pick(storm_id, verbs, "trackdir"))

    # Areas for longer-lived or major storms
    if len(areas_visited) >= 3 and (cat_num >= 3 or duration_days >= 5):
        unique_areas = list(dict.fromkeys(areas_visited))
        if len(unique_areas) >= 3:
            sentences.append(f"Its track spanned {', '.join(unique_areas[:4])}.")
        elif len(unique_areas) == 2:
            sentences.append(f"The storm journeyed from {unique_areas[0]} into {unique_areas[1]}.")

    if cat_num >= 3 and lat_range > 15:
        sentences.append(f"The storm covered a vast area, spanning roughly {round(lat_range)} degrees of latitude.")

    # ── INTENSIFICATION ───────────────────────────────────────
    if peak_wind > 0 and peak_cat > 0:
        peak_mph = int(peak_wind * 1.151)
        if rapid_intensification and cat_num >= 3:
            ri_mph = int(ri_amount * 1.151)
            phrase = pick(storm_id, INTENSIFICATION_PHRASES, "ri").format(cat=category_name(peak_cat))
            sentences.append(f"It {phrase} on {format_date_short(peak_date)}, with maximum sustained winds reaching {peak_mph} mph ({peak_wind} kt).")
        else:
            intens_templates = [
                f"It peaked as a {category_name(peak_cat)} on {format_date_short(peak_date)} with maximum sustained winds of {peak_mph} mph ({peak_wind} kt).",
                f"The storm reached {category_name(peak_cat)} strength on {format_date_short(peak_date)}, packing winds of {peak_mph} mph ({peak_wind} kt).",
                f"On {format_date_short(peak_date)}, it hit peak intensity as a {category_name(peak_cat)} with {peak_mph} mph ({peak_wind} kt) winds.",
            ]
            sentences.append(pick(storm_id, intens_templates, "intens"))
    elif peak_wind > 0:
        peak_mph = int(peak_wind * 1.151)
        sentences.append(f"It reached peak winds of {peak_mph} mph ({peak_wind} kt) on {format_date_short(peak_date)}.")

    # Pressure
    if min_pres_val and 0 < min_pres_val < 1010:
        if min_pres_val < 920:
            sentences.append(f"Its central pressure plunged to a remarkable {min_pres_val} mb — extraordinarily low, marking it among the most intense Atlantic hurricanes ever observed.")
        elif min_pres_val < 940:
            sentences.append(f"The minimum central pressure bottomed out at {min_pres_val} mb, a testament to the storm's ferocity.")
        elif min_pres_val < 970:
            sentences.append(f"Central pressure dropped to {min_pres_val} mb at the storm's peak.")
        else:
            sentences.append(f"The minimum central pressure was recorded at {min_pres_val} mb.")

    # ── LANDFALLS ─────────────────────────────────────────────
    if landfall_obs:
        for i, lf in enumerate(landfall_obs):
            area = get_landfall_area(lf["lat"], lf["lon"])
            lf_wind = lf["wind"] if lf["wind"] > 0 else 0
            lf_cat = saffir_simpson(lf_wind)
            if lf_wind > 0:
                lf_mph = int(lf_wind * 1.151)
                verb_template = pick(storm_id, LANDFALL_VERBS, f"lf{i}")
                verb = verb_template.format(area=area)
                if lf_cat > 0:
                    sentences.append(f"It {verb} on {format_date_short(lf['date'])} as a {category_name(lf_cat)} with {lf_mph} mph winds.")
                else:
                    sentences.append(f"It {verb} on {format_date_short(lf['date'])} with {lf_mph} mph winds.")
            else:
                sentences.append(f"It made landfall near {area} on {format_date_short(lf['date'])}.")
            if i >= 1 and len(landfall_obs) > 2:
                remaining = len(landfall_obs) - 2
                sentences.append(f"The storm made {remaining} additional landfall{'s' if remaining > 1 else ''} before finally weakening.")
                break
    elif num_landfalls > 0:
        sentences.append("The storm made landfall during its track.")
    elif cat_num >= 3:
        fishstorm = [
            "The storm remained over open water, threatening only shipping lanes.",
            "It stayed out to sea, never making landfall.",
            "Despite its power, it churned harmlessly over open ocean.",
        ]
        sentences.append(pick(storm_id, fishstorm, "fish"))

    # ── WEAKENING / DISSIPATION ───────────────────────────────
    if cat_num >= 2 and len(obs_list) >= 6:
        final_statuses = [o["status"] for o in obs_list[-4:]]
        if "EX" in final_statuses:
            sentences.append(pick(storm_id, WEAKENING_ET, "weak"))
        elif "TD" in final_statuses:
            sentences.append(pick(storm_id, WEAKENING_TD, "weak"))

    # Duration
    if duration_days >= 1:
        days_int = round(duration_days)
        if days_int >= 14:
            sentences.append(f"Remarkably, the system churned on for {days_int} days — an exceptionally long-lived cyclone.")
        elif days_int >= 10:
            sentences.append(f"The storm persisted for {days_int} days, making it notably long-lived.")
        elif days_int >= 2:
            sentences.append(f"The system lasted approximately {days_int} days.")
        else:
            sentences.append("The system persisted for approximately 1 day.")
    else:
        sentences.append("The system was short-lived, lasting less than a day.")

    # Dissipation
    if last_date != first_date:
        dissipation_area = get_basin_area(last_lat, last_lon)
        diss = pick(storm_id, DISSIPATION_PHRASES, "diss").format(area=dissipation_area, date=format_date_short(last_date))
        sentences.append(diss)

    # Observation count for unnamed storms
    if not is_named and len(obs_list) >= 2:
        sentences.append(f"The storm was tracked across {len(obs_list)} observations in the HURDAT2 database.")

    # ── NOTABLE BULLETS ───────────────────────────────────────
    notable_items = []

    if peak_cat == 5:
        notable_items.append("Reached Category 5 — one of only ~40 storms to achieve this in the Atlantic basin")
    if rapid_intensification:
        ri_mph = int(ri_amount * 1.151)
        notable_items.append(f"Underwent rapid intensification (winds increased ~{ri_mph} mph in 24 hours)")
    if min_pres_val and 0 < min_pres_val < 920:
        notable_items.append(f"Extremely low pressure of {min_pres_val} mb")
    if duration_days > 12:
        notable_items.append(f"Exceptionally long duration of {round(duration_days)} days")
    if len(landfall_obs) >= 3:
        notable_items.append(f"Made {len(landfall_obs)} landfalls")
    if is_named and name.upper() in RETIRED_NAMES:
        notable_items.append("Name was retired due to the storm's impact")
    if month_num in (11, 12):
        notable_items.append(f"Late-season storm ({'November' if month_num == 11 else 'December'})")
    elif month_num in (5, 6):
        notable_items.append(f"Early-season storm ({'May' if month_num == 5 else 'June'})")
    if landfall_obs:
        high_lat_lf = [o for o in landfall_obs if o["lat"] >= 40]
        if high_lat_lf:
            notable_items.append(f"Made landfall at unusually high latitude ({round(high_lat_lf[0]['lat'], 1)}°N)")

    # ── ENRICHMENT ────────────────────────────────────────────
    enrichment = ENRICHMENT.get(storm_id)
    if enrichment:
        if enrichment.get("impact"):
            sentences.append(enrichment["impact"])
        if enrichment.get("notable"):
            notable_items.extend(enrichment["notable"])

    # Append notable section
    if notable_items:
        notable_str = " | ".join(notable_items)
        sentences.append(f"Notable: {notable_str}")

    narrative = " ".join(sentences)
    return narrative


# ── Main ──────────────────────────────────────────────────────────

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

    # Remove narrative and is_retired from fields if they exist (we'll re-add them)
    base_fields = [f for f in original_fields if f not in ("narrative", "is_retired")]

    print("Generating narratives...")
    narr_count = 0
    retired_count = 0
    cat5_count = 0
    major_count = 0
    word_counts = []

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
        word_counts.append(len(narrative.split()))

        cat_num = int(row["category_num"]) if row["category_num"] else 0
        if cat_num == 5: cat5_count += 1
        if cat_num >= 3: major_count += 1

    # Write updated all CSV
    output_fields = base_fields + ["narrative", "is_retired"]
    print(f"Writing {ALL_CSV}...")
    with open(ALL_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)

    # Write 50yr CSV
    print(f"Writing {FIFTY_CSV}...")
    fifty_rows = [r for r in rows if int(r["year"]) >= 1976 and int(r["is_hurricane"]) == 1]
    with open(FIFTY_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(fifty_rows)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total storms processed:    {len(rows)}")
    print(f"Narratives generated:      {narr_count}")
    print(f"Retired names matched:     {retired_count}")
    print(f"Major hurricanes (Cat 3+): {major_count}")
    print(f"Category 5 hurricanes:     {cat5_count}")
    print(f"50-year file rows:         {len(fifty_rows)}")
    print(f"Enriched storms:           {len([k for k,v in ENRICHMENT.items() if v])}")
    print()

    # Word count stats
    print("WORD COUNT STATS")
    print("-" * 40)
    print(f"  Min:    {min(word_counts)} words")
    print(f"  Max:    {max(word_counts)} words")
    print(f"  Mean:   {sum(word_counts) / len(word_counts):.0f} words")
    print(f"  Median: {sorted(word_counts)[len(word_counts)//2]} words")
    total_words = sum(word_counts)
    print(f"  Total:  {total_words:,} words across {len(rows)} storms")
    print()

    # Sample narratives for requested storms
    target_ids = {
        "AL122005": "KATRINA 2005",
        "AL041900": "GALVESTON 1900",
        "AL182012": "SANDY 2012",
    }

    for sid, label in target_ids.items():
        for r in rows:
            if r["storm_id"] == sid:
                wc = len(r["narrative"].split())
                print(f"\n{'=' * 60}")
                print(f"  {label} ({sid}) — {wc} words")
                print(f"{'=' * 60}")
                print(r["narrative"])
                break

    # Find a weak TS for comparison
    print(f"\n{'=' * 60}")
    print("  RANDOM WEAK TROPICAL STORM")
    print(f"{'=' * 60}")
    for r in rows:
        cat = int(r["category_num"]) if r["category_num"] else 0
        wk = int(r["max_wind_kt"]) if r["max_wind_kt"] else 0
        if cat == 0 and 35 <= wk <= 45 and r["name"] != "UNNAMED" and int(r["year"]) >= 1990:
            wc = len(r["narrative"].split())
            print(f"  {r['name']} {r['year']} ({r['storm_id']}) — {wc} words")
            print(r["narrative"])
            break

    print("\nDone.")


if __name__ == "__main__":
    main()
