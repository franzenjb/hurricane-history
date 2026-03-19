"""
Upload hurricane track line segments GeoJSON to AGOL.
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
    body += f'Content-Type: application/geo+json\r\n\r\n'.encode()
    with open(file_path, 'rb') as f:
        body += f.read()
    body += b'\r\n'
    body += f'--{boundary}--\r\n'.encode()

    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode())

def main():
    token = get_token()
    geojson_path = os.path.join(os.path.dirname(__file__), "atlantic_hurricane_track_segments.geojson")
    size_mb = os.path.getsize(geojson_path) / 1024 / 1024
    print(f"Uploading: {geojson_path} ({size_mb:.1f} MB)")

    # Step 1: Upload GeoJSON
    add_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/addItem"
    fields = {
        'f': 'json',
        'token': token,
        'type': 'GeoJson',
        'title': 'Atlantic Hurricane Track Segments 1851-2025 (HURDAT2)',
        'tags': 'hurricanes,NOAA,HURDAT2,Atlantic,weather,disasters,NHC,tracks,storm paths,animated',
        'description': 'Polyline segments for all 1,973 Atlantic tropical cyclone tracks 1851-2025. '
                       '53,601 segments — each 6-hour step is a separate line carrying its own intensity. '
                       'Color by category_num for paths that shift from blue (TD) to red (Cat 5) as storms intensify. '
                       'Includes peak_category_num for filtering by storm strength. '
                       'Use with Symbol Animation for animated storm paths. '
                       'Source: NOAA NHC HURDAT2 (nhc.noaa.gov/data/hurdat/)',
        'snippet': '53,601 track segments for all Atlantic storms 1851-2025 — color by intensity, animate paths',
    }

    result = multipart_upload(add_url, fields, geojson_path)
    if not result.get('success'):
        raise Exception(f"Upload failed: {result}")
    item_id = result['id']
    print(f"GeoJSON uploaded: {item_id}")

    # Step 2: Publish
    publish_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/publish"
    pub_params = {
        'name': 'Atlantic_Hurricane_Track_Segments_1851_2025',
        'maxRecordCount': 10000,
        'targetSR': {'wkid': 4326},
    }

    publish_data = urllib.parse.urlencode({
        'f': 'json',
        'token': token,
        'itemType': 'file',
        'filetype': 'geojson',
        'itemId': item_id,
        'publishParameters': json.dumps(pub_params),
    }).encode()
    req = urllib.request.Request(publish_url, data=publish_data)
    with urllib.request.urlopen(req, timeout=300) as resp:
        pub_result = json.loads(resp.read().decode())

    if pub_result.get('error'):
        raise Exception(f"Publish failed: {pub_result}")

    services = pub_result.get('services', [])
    if not services:
        print(f"Response: {json.dumps(pub_result, indent=2)}")
        return

    svc = services[0]
    svc_item_id = svc.get('serviceItemId')
    svc_url = svc.get('serviceurl')
    job_id = svc.get('jobId')
    print(f"\nPublishing 53K segments...")
    print(f"  Item ID: {svc_item_id}")
    print(f"  Service URL: {svc_url}")

    # Step 3: Wait
    if job_id and svc_item_id:
        for i in range(90):
            status_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/items/{svc_item_id}/status"
            status_data = urllib.parse.urlencode({
                'f': 'json', 'token': token,
                'jobId': job_id, 'jobType': 'publish',
            }).encode()
            req = urllib.request.Request(status_url, data=status_data)
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = json.loads(resp.read().decode())
            s = status.get('status', '')
            if i % 5 == 0 or s in ('completed', 'failed'):
                print(f"  Status: {s} ({i * 3}s)")
            if s == 'completed':
                break
            elif s == 'failed':
                raise Exception(f"Publish failed: {status}")
            time.sleep(3)

    # Step 4: Verify
    query_url = f"{svc_url}/0/query"
    count_data = urllib.parse.urlencode({
        'f': 'json', 'token': token,
        'where': '1=1', 'returnCountOnly': 'true'
    }).encode()
    req = urllib.request.Request(query_url, data=count_data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        count = json.loads(resp.read().decode())
    print(f"\nDone! {count.get('count'):,} line segments published.")
    print(f"View: {AGOL_BASE}/home/item.html?id={svc_item_id}")

if __name__ == "__main__":
    main()
