"""
Populate the new fields (narrative, is_retired, landfall_state) in existing AGOL layers.
The layers already have the features — we just need to update the new field values.
"""

import urllib.request
import urllib.parse
import json
import csv
import os
import time

AGOL_BASE = "https://services7.arcgis.com/1J4A0YH8gSNAmQVQ/arcgis/rest/services"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_token():
    with open('/tmp/giscorps_token.txt', 'r') as f:
        return f.read().strip()

def batch_update(layer_url, token, updates, batch_size=200):
    """Update features in batches."""
    total = 0
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]
        url = f"{layer_url}/updateFeatures"
        data = urllib.parse.urlencode({
            'f': 'json',
            'token': token,
            'features': json.dumps(batch),
            'rollbackOnFailure': 'false'
        }).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
        successes = sum(1 for r in result.get('updateResults', []) if r.get('success'))
        total += successes
        if (i // batch_size) % 10 == 0 or i + batch_size >= len(updates):
            print(f"  Batch {i//batch_size + 1}: {successes}/{len(batch)} updated (total: {total:,})")
    return total


def populate_summary(token):
    """Populate narrative and is_retired fields in the summary table."""
    print("\n=== Populating Summary Table (narrative + is_retired) ===")
    layer_url = f"{AGOL_BASE}/Atlantic_Hurricanes_1851_2025/FeatureServer/0"

    # Read CSV data
    csv_path = os.path.join(PROJECT_DIR, "atlantic_hurricanes_all.csv")
    csv_data = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            csv_data[row['storm_id']] = {
                'narrative': row.get('narrative', ''),
                'is_retired': int(row.get('is_retired', 0))
            }

    # Query all existing features to get ObjectIDs
    print("  Querying existing features...")
    all_features = []
    offset = 0
    while True:
        q_url = f"{layer_url}/query"
        q_data = urllib.parse.urlencode({
            'f': 'json', 'token': token,
            'where': '1=1',
            'outFields': 'storm_id,ObjectId',
            'returnGeometry': 'false',
            'resultOffset': offset,
            'resultRecordCount': 2000
        }).encode()
        req = urllib.request.Request(q_url, data=q_data)
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        features = result.get('features', [])
        if not features:
            break
        all_features.extend(features)
        offset += len(features)
        if not result.get('exceededTransferLimit', False):
            break

    print(f"  Found {len(all_features):,} features")

    # Build update payloads
    updates = []
    for f in all_features:
        storm_id = f['attributes']['storm_id']
        oid = f['attributes']['ObjectId']
        if storm_id in csv_data:
            updates.append({
                'attributes': {
                    'ObjectId': oid,
                    'narrative': csv_data[storm_id]['narrative'],
                    'is_retired': csv_data[storm_id]['is_retired']
                }
            })

    print(f"  Updating {len(updates):,} features...")
    total = batch_update(layer_url, token, updates, batch_size=100)
    print(f"  Done: {total:,} features updated")


def populate_tracks(token):
    """Populate landfall_state field in the track points layer."""
    print("\n=== Populating Track Points (landfall_state) ===")
    layer_url = f"{AGOL_BASE}/Atlantic_Hurricane_Tracks_1851_2025/FeatureServer/0"

    # Read CSV — only need landfall points with state values
    csv_path = os.path.join(PROJECT_DIR, "atlantic_hurricane_tracks.csv")
    landfall_data = {}  # key: (storm_id, datetime) -> landfall_state
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            if row['is_landfall'] == '1' and row.get('landfall_state', ''):
                key = (row['storm_id'], row['datetime'])
                landfall_data[key] = row['landfall_state']

    print(f"  Landfall points with state data: {len(landfall_data):,}")

    # Query only landfall features from AGOL
    print("  Querying landfall features...")
    all_landfalls = []
    offset = 0
    while True:
        q_url = f"{layer_url}/query"
        q_data = urllib.parse.urlencode({
            'f': 'json', 'token': token,
            'where': 'is_landfall = 1',
            'outFields': 'storm_id,datetime,ObjectId',
            'returnGeometry': 'false',
            'resultOffset': offset,
            'resultRecordCount': 2000
        }).encode()
        req = urllib.request.Request(q_url, data=q_data)
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        features = result.get('features', [])
        if not features:
            break
        all_landfalls.extend(features)
        offset += len(features)
        if not result.get('exceededTransferLimit', False):
            break

    print(f"  Found {len(all_landfalls):,} landfall features in AGOL")

    # Match and build updates
    updates = []
    matched = 0
    for f in all_landfalls:
        attrs = f['attributes']
        storm_id = attrs['storm_id']
        dt = attrs['datetime']

        # datetime from AGOL might be epoch ms — convert to string for matching
        if isinstance(dt, (int, float)):
            from datetime import datetime, timezone
            dt_obj = datetime.fromtimestamp(dt / 1000, tz=timezone.utc)
            dt_str = dt_obj.strftime("%Y-%m-%d %H:%M")
        else:
            dt_str = str(dt)

        key = (storm_id, dt_str)
        if key in landfall_data:
            updates.append({
                'attributes': {
                    'ObjectId': attrs['ObjectId'],
                    'landfall_state': landfall_data[key]
                }
            })
            matched += 1

    print(f"  Matched {matched:,} landfall features to state data")

    if updates:
        print(f"  Updating {len(updates):,} features...")
        total = batch_update(layer_url, token, updates, batch_size=200)
        print(f"  Done: {total:,} features updated")
    else:
        print("  No updates needed")


def main():
    token = get_token()
    populate_summary(token)
    populate_tracks(token)
    print("\n=== All field population complete! ===")


if __name__ == "__main__":
    main()
