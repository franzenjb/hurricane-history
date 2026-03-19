"""
Overwrite existing AGOL hosted feature layers with updated CSVs.
Uses the AGOL REST API overwrite endpoint to replace data + schema.
"""

import urllib.request
import urllib.parse
import json
import os
import time

AGOL_BASE = "https://franzengiscorp.maps.arcgis.com"
USERNAME = "jefffranzen_giscorp"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Existing service item IDs
SUMMARY_ITEM_ID = "08a82646b8fc45d691fd9524b4b6d36c"
TRACKS_ITEM_ID = "a62e3d140b614ced8509168434a0d90e"

def get_token():
    with open('/tmp/giscorps_token.txt', 'r') as f:
        return f.read().strip()

def multipart_upload(url, fields, file_path, file_field='file'):
    """Upload a file via multipart/form-data."""
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body = b''
    for key, val in fields.items():
        body += f'--{boundary}\r\n'.encode()
        body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
        body += f'{val}\r\n'.encode()

    filename = os.path.basename(file_path)
    body += f'--{boundary}\r\n'.encode()
    body += f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode()
    body += f'Content-Type: text/csv\r\n\r\n'.encode()
    with open(file_path, 'rb') as f:
        body += f.read()
    body += b'\r\n'
    body += f'--{boundary}--\r\n'.encode()

    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())


def find_source_item(token, service_item_id):
    """Find the source CSV item ID that backs a hosted feature service."""
    url = f"{AGOL_BASE}/sharing/rest/content/items/{service_item_id}"
    data = urllib.parse.urlencode({'f': 'json', 'token': token}).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req) as resp:
        item = json.loads(resp.read())
    # Check for related items (the source CSV)
    rel_url = f"{AGOL_BASE}/sharing/rest/content/items/{service_item_id}/relatedItems"
    data = urllib.parse.urlencode({
        'f': 'json', 'token': token,
        'relationshipType': 'Service2Data', 'direction': 'forward'
    }).encode()
    req = urllib.request.Request(rel_url, data=data)
    with urllib.request.urlopen(req) as resp:
        rel = json.loads(resp.read())
    related = rel.get('relatedItems', [])
    for r in related:
        if r.get('type') == 'CSV':
            return r['id']
    return None


def overwrite_layer(token, service_item_id, csv_path, layer_name, is_spatial=False):
    """Overwrite a hosted feature layer by updating its source CSV and republishing."""
    print(f"\n{'='*50}")
    print(f"Overwriting: {layer_name}")
    print(f"  CSV: {csv_path} ({os.path.getsize(csv_path) / 1024 / 1024:.1f} MB)")
    print(f"  Service Item: {service_item_id}")

    # Find the source CSV item
    source_csv_id = find_source_item(token, service_item_id)
    if source_csv_id:
        print(f"  Source CSV Item: {source_csv_id}")
        # Update the source CSV with new file
        update_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/items/{source_csv_id}/update"
        result = multipart_upload(update_url, {
            'f': 'json',
            'token': token,
        }, csv_path)
        if not result.get('success'):
            print(f"  Warning: Source CSV update failed: {result}")
    else:
        print("  No source CSV found — will upload new")

    # Use the overwrite endpoint on the feature service
    overwrite_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/items/{service_item_id}/overwrite"

    # Build publish parameters
    pub_params = {
        'name': layer_name,
        'maxRecordCount': 10000 if is_spatial else 2100,
    }
    if is_spatial:
        pub_params['locationType'] = 'coordinates'
        pub_params['latitudeFieldName'] = 'latitude'
        pub_params['longitudeFieldName'] = 'longitude'

    result = multipart_upload(overwrite_url, {
        'f': 'json',
        'token': token,
        'publishParameters': json.dumps(pub_params),
    }, csv_path)

    if result.get('error'):
        print(f"  Overwrite error: {result['error']}")
        # Try alternative: update data via truncate + append
        print("  Trying truncate + append fallback...")
        truncate_and_append(token, service_item_id, csv_path, is_spatial)
        return

    print(f"  Overwrite initiated: {json.dumps(result, indent=2)[:300]}")

    # Wait for completion
    if result.get('jobId'):
        wait_for_job(token, service_item_id, result['jobId'])

    # Verify
    verify_layer(token, service_item_id)


def truncate_and_append(token, service_item_id, csv_path, is_spatial):
    """Fallback: truncate existing features and append from CSV."""
    # Get the service URL
    url = f"{AGOL_BASE}/sharing/rest/content/items/{service_item_id}"
    data = urllib.parse.urlencode({'f': 'json', 'token': token}).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req) as resp:
        item = json.loads(resp.read())
    svc_url = item.get('url', '')
    if not svc_url:
        raise Exception("No service URL found")

    layer_url = f"{svc_url}/0"

    # First, add missing fields
    print("  Adding new fields if needed...")
    add_fields_if_missing(token, layer_url, csv_path)

    # Truncate
    print("  Truncating existing features...")
    trunc_url = f"{layer_url}/truncate"
    trunc_data = urllib.parse.urlencode({
        'f': 'json', 'token': token, 'isAsync': 'false'
    }).encode()
    req = urllib.request.Request(trunc_url, data=trunc_data)
    with urllib.request.urlopen(req, timeout=120) as resp:
        trunc_result = json.loads(resp.read())
    print(f"  Truncate result: {trunc_result}")

    # Append via addFeatures in batches
    print("  Appending features from CSV...")
    import csv
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    batch_size = 500
    total_added = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        features = []
        for row in batch:
            attrs = {}
            for k, v in row.items():
                if v == '':
                    attrs[k] = None
                else:
                    # Try numeric conversion
                    try:
                        if '.' in v:
                            attrs[k] = float(v)
                        else:
                            attrs[k] = int(v)
                    except ValueError:
                        attrs[k] = v

            feature = {"attributes": attrs}
            if is_spatial and 'latitude' in attrs and 'longitude' in attrs:
                lat = attrs.pop('latitude', None)
                lon = attrs.pop('longitude', None)
                if lat is not None and lon is not None:
                    feature['geometry'] = {"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}
                    attrs['latitude'] = lat
                    attrs['longitude'] = lon

            features.append(feature)

        add_url = f"{layer_url}/addFeatures"
        add_data = urllib.parse.urlencode({
            'f': 'json', 'token': token,
            'features': json.dumps(features),
            'rollbackOnFailure': 'true'
        }).encode()
        req = urllib.request.Request(add_url, data=add_data)
        with urllib.request.urlopen(req, timeout=120) as resp:
            add_result = json.loads(resp.read())

        added = sum(1 for r in add_result.get('addResults', []) if r.get('success'))
        total_added += added
        print(f"    Batch {i//batch_size + 1}: {added}/{len(batch)} added (total: {total_added:,})")

    print(f"  Done: {total_added:,} features added")


def add_fields_if_missing(token, layer_url, csv_path):
    """Add new fields to the layer definition if they don't exist yet."""
    # Get current fields
    fields_url = f"{layer_url}?f=json&token={token}"
    req = urllib.request.Request(fields_url)
    with urllib.request.urlopen(req) as resp:
        layer_def = json.loads(resp.read())

    existing_fields = {f['name'].lower() for f in layer_def.get('fields', [])}

    # Read CSV headers
    with open(csv_path) as f:
        headers = f.readline().strip().split(',')

    # Determine new fields
    new_fields = []
    for h in headers:
        if h.lower() not in existing_fields:
            # Guess type from first non-empty value
            field_type = "esriFieldTypeString"
            if h in ('is_retired',):
                field_type = "esriFieldTypeInteger"
            new_fields.append({
                "name": h,
                "type": field_type,
                "alias": h.replace('_', ' ').title(),
                "sqlType": "sqlTypeOther",
                "length": 4000 if field_type == "esriFieldTypeString" else None,
                "nullable": True,
                "editable": True,
            })

    if not new_fields:
        print("    No new fields needed")
        return

    print(f"    Adding {len(new_fields)} new fields: {[f['name'] for f in new_fields]}")

    admin_url = layer_url.replace('/rest/services/', '/rest/admin/services/')
    add_url = f"{admin_url}/addToDefinition"
    add_data = urllib.parse.urlencode({
        'f': 'json', 'token': token,
        'addToDefinition': json.dumps({"fields": new_fields})
    }).encode()
    req = urllib.request.Request(add_url, data=add_data)
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    print(f"    Add fields result: {result}")


def wait_for_job(token, item_id, job_id):
    """Wait for an async job to complete."""
    for i in range(60):
        status_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/items/{item_id}/status"
        data = urllib.parse.urlencode({
            'f': 'json', 'token': token,
            'jobId': job_id, 'jobType': 'publish',
        }).encode()
        req = urllib.request.Request(status_url, data=data)
        with urllib.request.urlopen(req) as resp:
            status = json.loads(resp.read())
        s = status.get('status', '')
        print(f"  Status: {s}")
        if s == 'completed':
            return
        elif s == 'failed':
            raise Exception(f"Job failed: {status}")
        time.sleep(3)


def verify_layer(token, item_id):
    """Query the layer to verify feature count."""
    url = f"{AGOL_BASE}/sharing/rest/content/items/{item_id}"
    data = urllib.parse.urlencode({'f': 'json', 'token': token}).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req) as resp:
        item = json.loads(resp.read())

    svc_url = item.get('url', '')
    if svc_url:
        count_url = f"{svc_url}/0/query"
        count_data = urllib.parse.urlencode({
            'f': 'json', 'token': token,
            'where': '1=1', 'returnCountOnly': 'true'
        }).encode()
        req = urllib.request.Request(count_url, data=count_data)
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"  Feature count: {result.get('count', 'unknown'):,}")

        # Check for new fields
        fields_url = f"{svc_url}/0?f=json&token={token}"
        req = urllib.request.Request(fields_url)
        with urllib.request.urlopen(req) as resp:
            layer_def = json.loads(resp.read())
        field_names = [f['name'] for f in layer_def.get('fields', [])]
        print(f"  Fields: {', '.join(field_names)}")


def main():
    token = get_token()

    # 1. Overwrite summary table
    summary_csv = os.path.join(PROJECT_DIR, "atlantic_hurricanes_all.csv")
    overwrite_layer(token, SUMMARY_ITEM_ID, summary_csv,
                    "Atlantic_Hurricanes_1851_2025", is_spatial=False)

    # 2. Overwrite track points
    tracks_csv = os.path.join(PROJECT_DIR, "atlantic_hurricane_tracks.csv")
    overwrite_layer(token, TRACKS_ITEM_ID, tracks_csv,
                    "Atlantic_Hurricane_Tracks_1851_2025", is_spatial=True)

    print("\n" + "="*50)
    print("AGOL overwrite complete!")


if __name__ == "__main__":
    main()
