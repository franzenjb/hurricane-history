"""
Enrich hurricane track points with landfall state/country via spatial join.

For each track point where is_landfall=1, does a point-in-polygon lookup against:
  1. US Census state boundaries (cb_2022_us_state_500k)
  2. Natural Earth country boundaries (ne_50m_admin_0_countries)

Adds a `landfall_state` column:
  - US state name if landfall is in a US state
  - Country name if landfall is outside the US
  - Empty string for non-landfall points or unmatched points
"""

import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# Paths
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
CSV_PATH = os.path.join(PROJECT_DIR, "atlantic_hurricane_tracks.csv")

# URLs for boundary data
STATES_URL = "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_state_500k.zip"
COUNTRIES_URL = "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip"

# Local cache paths
STATES_PATH = os.path.join(DATA_DIR, "cb_2022_us_state_500k.zip")
COUNTRIES_PATH = os.path.join(DATA_DIR, "ne_50m_admin_0_countries.zip")


def download_if_needed(url, local_path):
    """Download a file if it doesn't already exist locally."""
    if os.path.exists(local_path):
        print(f"  Using cached: {os.path.basename(local_path)}")
        return
    print(f"  Downloading: {os.path.basename(local_path)}...")
    import urllib.request
    urllib.request.urlretrieve(url, local_path)
    print(f"  Saved to: {local_path}")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # --- Load boundary data ---
    print("Loading boundary data...")
    download_if_needed(STATES_URL, STATES_PATH)
    download_if_needed(COUNTRIES_URL, COUNTRIES_PATH)

    print("  Reading US states shapefile...")
    states = gpd.read_file(STATES_PATH)
    states = states.to_crs(epsg=4326)  # ensure WGS84

    print("  Reading Natural Earth countries shapefile...")
    countries = gpd.read_file(COUNTRIES_PATH)
    countries = countries.to_crs(epsg=4326)

    # Exclude US from countries layer (we use the more detailed Census states for US)
    countries_non_us = countries[countries["ISO_A2"] != "US"].copy()

    # --- Load track points ---
    print(f"\nLoading track points from {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    total_rows = len(df)
    print(f"  Total rows: {total_rows:,}")

    # Filter to landfall points only for the spatial join
    landfall_mask = df["is_landfall"] == 1
    landfall_df = df[landfall_mask].copy()
    n_landfalls = len(landfall_df)
    print(f"  Landfall points: {n_landfalls:,}")

    # Create GeoDataFrame from landfall points
    geometry = [Point(lon, lat) for lon, lat in zip(landfall_df["longitude"], landfall_df["latitude"])]
    landfall_gdf = gpd.GeoDataFrame(landfall_df, geometry=geometry, crs="EPSG:4326")

    # --- Spatial join: US states ---
    print("\nRunning spatial join against US states...")
    joined_states = gpd.sjoin(landfall_gdf, states[["NAME", "geometry"]], how="left", predicate="within")
    # NAME from states layer = state name
    joined_states = joined_states.rename(columns={"NAME": "state_name"})
    # Drop duplicates if a point falls in overlapping polygons (take first match)
    joined_states = joined_states[~joined_states.index.duplicated(keep="first")]

    # --- Spatial join: countries (non-US) ---
    print("Running spatial join against country boundaries...")
    # Only run on points that didn't match a US state
    unmatched_mask = joined_states["state_name"].isna()
    unmatched_gdf = landfall_gdf.loc[joined_states[unmatched_mask].index].copy()

    country_name_col = "NAME"  # Natural Earth uses NAME for country name
    joined_countries = gpd.sjoin(unmatched_gdf, countries_non_us[[country_name_col, "geometry"]], how="left", predicate="within")
    joined_countries = joined_countries.rename(columns={country_name_col: "country_name"})
    joined_countries = joined_countries[~joined_countries.index.duplicated(keep="first")]

    # --- Combine results ---
    print("Combining results...")
    # Start with state names
    landfall_df["landfall_state"] = joined_states["state_name"].values

    # Fill in country names where state is NaN
    unmatched_indices = landfall_df["landfall_state"].isna()
    # Map country results back by index
    country_lookup = joined_countries["country_name"]
    for idx in landfall_df[unmatched_indices].index:
        if idx in country_lookup.index and pd.notna(country_lookup.loc[idx]):
            landfall_df.at[idx, "landfall_state"] = country_lookup.loc[idx]

    # Fill remaining NaN with empty string
    landfall_df["landfall_state"] = landfall_df["landfall_state"].fillna("")

    # --- Try buffered lookup for still-unmatched landfall points ---
    still_empty = landfall_df["landfall_state"] == ""
    n_empty = still_empty.sum()
    if n_empty > 0:
        print(f"\n  {n_empty} landfall points unmatched — trying 0.1° buffer lookup...")
        empty_gdf = landfall_gdf.loc[landfall_df[still_empty].index].copy()

        # Buffer the points slightly to catch near-coast landfalls
        buffered = empty_gdf.copy()
        buffered["geometry"] = buffered.geometry.buffer(0.1)

        # Try states first
        buf_states = gpd.sjoin(buffered, states[["NAME", "geometry"]], how="left", predicate="intersects")
        buf_states = buf_states[~buf_states.index.duplicated(keep="first")]

        # Then countries for remaining
        buf_unmatched = buf_states[buf_states["NAME"].isna()]
        if len(buf_unmatched) > 0:
            buf_countries = gpd.sjoin(
                buffered.loc[buf_unmatched.index],
                countries_non_us[[country_name_col, "geometry"]],
                how="left",
                predicate="intersects"
            )
            buf_countries = buf_countries[~buf_countries.index.duplicated(keep="first")]
        else:
            buf_countries = pd.DataFrame()

        # Apply buffered results
        for idx in landfall_df[still_empty].index:
            if idx in buf_states.index and pd.notna(buf_states.at[idx, "NAME"]):
                landfall_df.at[idx, "landfall_state"] = buf_states.at[idx, "NAME"]
            elif len(buf_countries) > 0 and idx in buf_countries.index and pd.notna(buf_countries.at[idx, country_name_col]):
                landfall_df.at[idx, "landfall_state"] = buf_countries.at[idx, country_name_col]

    # --- Merge back into full dataframe ---
    df["landfall_state"] = ""
    df.loc[landfall_mask, "landfall_state"] = landfall_df["landfall_state"].values

    # --- Stats ---
    assigned = df[(df["is_landfall"] == 1) & (df["landfall_state"] != "")]
    unassigned = df[(df["is_landfall"] == 1) & (df["landfall_state"] == "")]
    print(f"\n=== RESULTS ===")
    print(f"  Landfall points with state/country: {len(assigned):,}")
    print(f"  Landfall points unmatched: {len(unassigned):,}")
    print(f"  Match rate: {len(assigned)/n_landfalls*100:.1f}%")

    # Top landfall locations
    print(f"\n=== TOP LANDFALL LOCATIONS ===")
    top = df[df["landfall_state"] != ""]["landfall_state"].value_counts().head(15)
    for loc, count in top.items():
        print(f"  {loc}: {count}")

    # --- Verification: specific storms ---
    print(f"\n=== VERIFICATION ===")
    for storm_name, expected in [
        ("KATRINA", "Florida + Louisiana"),
        ("ANDREW", "Florida + Louisiana"),
        ("HARVEY", "Texas"),
        ("SANDY", "New Jersey/New York area"),
    ]:
        storm_landfalls = df[(df["name"] == storm_name) & (df["is_landfall"] == 1)]
        if len(storm_landfalls) == 0:
            print(f"\n  {storm_name}: No landfall records found")
            continue
        # Show all instances (multiple storms may share a name)
        for _, row in storm_landfalls.iterrows():
            print(f"  {storm_name} ({row['year']}): lat={row['latitude']}, lon={row['longitude']}, "
                  f"wind={row['wind_mph']}mph, landfall_state=\"{row['landfall_state']}\"")
        print(f"    Expected: {expected}")

    # --- Write updated CSV ---
    print(f"\nWriting updated CSV to {CSV_PATH}...")
    df.to_csv(CSV_PATH, index=False)
    print("Done!")

    # Show any remaining unmatched for debugging
    if len(unassigned) > 0:
        print(f"\n=== SAMPLE UNMATCHED LANDFALLS (up to 10) ===")
        sample = unassigned.head(10)
        for _, row in sample.iterrows():
            print(f"  {row['name']} ({row['year']}): lat={row['latitude']}, lon={row['longitude']}")


if __name__ == "__main__":
    main()
