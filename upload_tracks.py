"""
Upload hurricane track points CSV to AGOL as a spatial feature layer.
"""

import urllib.request
import urllib.parse
import json
import os
import time

AGOL_BASE = "https://franzengiscorp.maps.arcgis.com"
USERNAME = "jefffranzen_giscorp"

def get_token():
    with open('/tmp/giscorps_token.txt', 'r') as f:
        return f.read().strip()

def multipart_upload(url, fields, file_path, file_field='file'):
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
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())

def main():
    token = get_token()
    csv_path = os.path.join(os.path.dirname(__file__), "atlantic_hurricane_tracks.csv")
    print(f"Uploading: {csv_path} ({os.path.getsize(csv_path) / 1024 / 1024:.1f} MB)")

    # Step 1: Upload CSV
    add_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/addItem"
    fields = {
        'f': 'json',
        'token': token,
        'type': 'CSV',
        'title': 'Atlantic Hurricane Tracks 1851-2025 (HURDAT2)',
        'tags': 'hurricanes,NOAA,HURDAT2,Atlantic,weather,disasters,NHC,tracks,storm paths',
        'description': 'Every 6-hour track observation for all 2,004 Atlantic tropical cyclones 1851-2025. '
                       '55,605 points with lat/lon, wind speed, pressure, Saffir-Simpson category, '
                       'and landfall flag. Parsed from NOAA NHC HURDAT2 database. '
                       'Source: nhc.noaa.gov/data/hurdat/',
        'snippet': '55,605 track points for all Atlantic storms 1851-2025 — lat/lon, wind, pressure, category, landfall flag',
    }

    result = multipart_upload(add_url, fields, csv_path)
    if not result.get('success'):
        raise Exception(f"Upload failed: {result}")
    csv_item_id = result['id']
    print(f"CSV uploaded: {csv_item_id}")

    # Step 2: Analyze
    analyze_url = f"{AGOL_BASE}/sharing/rest/content/features/analyze"
    analyze_data = urllib.parse.urlencode({
        'f': 'json',
        'token': token,
        'itemid': csv_item_id,
        'filetype': 'csv',
        'analyzeParameters': json.dumps({
            'enableGlobalGeocoding': False,
            'sourceLocale': 'en',
            'latitudeFieldName': 'latitude',
            'longitudeFieldName': 'longitude',
        })
    }).encode()
    req = urllib.request.Request(analyze_url, data=analyze_data)
    with urllib.request.urlopen(req, timeout=120) as resp:
        analyze_result = json.loads(resp.read().decode())

    pub_params = analyze_result.get('publishParameters', {})
    pub_params['name'] = 'Atlantic_Hurricane_Tracks_1851_2025'
    pub_params['maxRecordCount'] = 10000

    # Ensure lat/lon location info is set
    if 'locationType' not in pub_params:
        pub_params['locationType'] = 'coordinates'
        pub_params['latitudeFieldName'] = 'latitude'
        pub_params['longitudeFieldName'] = 'longitude'

    print(f"Location type: {pub_params.get('locationType')}")
    print(f"Lat field: {pub_params.get('latitudeFieldName')}")
    print(f"Lon field: {pub_params.get('longitudeFieldName')}")

    # Step 3: Publish
    publish_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/publish"
    publish_data = urllib.parse.urlencode({
        'f': 'json',
        'token': token,
        'itemType': 'csv',
        'filetype': 'csv',
        'itemId': csv_item_id,
        'publishParameters': json.dumps(pub_params),
    }).encode()
    req = urllib.request.Request(publish_url, data=publish_data)
    with urllib.request.urlopen(req, timeout=300) as resp:
        pub_result = json.loads(resp.read().decode())

    if pub_result.get('error'):
        raise Exception(f"Publish failed: {pub_result}")

    services = pub_result.get('services', [])
    if not services:
        print(f"Unexpected response: {json.dumps(pub_result, indent=2)}")
        return

    svc = services[0]
    svc_item_id = svc.get('serviceItemId')
    svc_url = svc.get('serviceurl')
    job_id = svc.get('jobId')
    print(f"\nPublishing...")
    print(f"  Item ID: {svc_item_id}")
    print(f"  Service URL: {svc_url}")

    # Step 4: Wait for completion
    if job_id and svc_item_id:
        for i in range(60):
            status_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/items/{svc_item_id}/status"
            status_data = urllib.parse.urlencode({
                'f': 'json', 'token': token,
                'jobId': job_id, 'jobType': 'publish',
            }).encode()
            req = urllib.request.Request(status_url, data=status_data)
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = json.loads(resp.read().decode())
            s = status.get('status', '')
            print(f"  Status: {s}")
            if s == 'completed':
                break
            elif s == 'failed':
                raise Exception(f"Publish failed: {status}")
            time.sleep(3)

    # Step 5: Verify
    query_url = f"{svc_url}/0/query"
    count_data = urllib.parse.urlencode({
        'f': 'json', 'token': token,
        'where': '1=1', 'returnCountOnly': 'true'
    }).encode()
    req = urllib.request.Request(query_url, data=count_data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        count = json.loads(resp.read().decode())
    print(f"\nDone! {count.get('count'):,} features published.")
    print(f"View: {AGOL_BASE}/home/item.html?id={svc_item_id}")

if __name__ == "__main__":
    main()
