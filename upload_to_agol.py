"""
Upload Atlantic hurricane CSV to ArcGIS Online (GISCorps account).
Creates a hosted table, then publishes as a hosted feature layer.
"""

import urllib.request
import urllib.parse
import json
import os
import mimetypes

AGOL_BASE = "https://franzengiscorp.maps.arcgis.com"
USERNAME = "jefffranzen_giscorp"

# Read saved OAuth token
def get_token():
    with open('/tmp/giscorps_token.txt', 'r') as f:
        token = f.read().strip()
    if not token:
        raise Exception("No token found at /tmp/giscorps_token.txt")
    print(f"Using saved GISCorps OAuth token")
    return token

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
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())

def main():
    token = get_token()

    csv_path = os.path.join(os.path.dirname(__file__), "atlantic_hurricanes_all.csv")
    print(f"Uploading: {csv_path}")

    # Step 1: Add CSV as item
    add_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/addItem"
    fields = {
        'f': 'json',
        'token': token,
        'type': 'CSV',
        'title': 'Atlantic Hurricanes 1851-2025 (HURDAT2)',
        'tags': 'hurricanes,NOAA,HURDAT2,Atlantic,weather,disasters,NHC,climate',
        'description': 'Complete Atlantic basin tropical cyclone history from 1851-2025. '
                       'Parsed from NOAA National Hurricane Center HURDAT2 database. '
                       '2,004 storms — tropical depressions through Category 5. '
                       'One row per storm with peak category, max wind, min pressure, '
                       'duration, and landfall count. Source: nhc.noaa.gov/data/hurdat/',
        'snippet': 'All 2,004 Atlantic tropical cyclones 1851-2025 from NOAA HURDAT2 — full history with category, wind, pressure',
    }

    result = multipart_upload(add_url, fields, csv_path)
    if not result.get('success'):
        raise Exception(f"Upload failed: {result}")

    item_id = result['id']
    print(f"CSV uploaded as item: {item_id}")

    # Step 2: Publish as hosted feature layer (table with no geometry)
    publish_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/publish"
    publish_params = {
        'name': 'Atlantic_Hurricanes_1851_2025',
        'maxRecordCount': 2000,
        'layerInfo': {
            'capabilities': 'Query',
        }
    }

    publish_data = urllib.parse.urlencode({
        'f': 'json',
        'token': token,
        'itemType': 'csv',
        'filetype': 'csv',
        'itemId': item_id,
        'publishParameters': json.dumps(publish_params),
    }).encode()

    req = urllib.request.Request(publish_url, data=publish_data)
    with urllib.request.urlopen(req, timeout=120) as resp:
        pub_result = json.loads(resp.read().decode())

    if pub_result.get('error'):
        raise Exception(f"Publish failed: {pub_result}")

    services = pub_result.get('services', [])
    if services:
        svc = services[0]
        svc_item_id = svc.get('serviceItemId')
        svc_url = svc.get('serviceurl')
        job_id = svc.get('jobId')
        print(f"\nPublished!")
        print(f"  Item ID: {svc_item_id}")
        print(f"  Service URL: {svc_url}")
        print(f"  Job ID: {job_id}")
        print(f"\n  View item: {AGOL_BASE}/home/item.html?id={svc_item_id}")

        # Step 3: Check publish status
        if job_id:
            status_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/items/{svc_item_id}/status"
            import time
            for i in range(30):
                status_data = urllib.parse.urlencode({
                    'f': 'json',
                    'token': token,
                    'jobId': job_id,
                    'jobType': 'publish',
                }).encode()
                req = urllib.request.Request(status_url, data=status_data)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    status = json.loads(resp.read().decode())
                s = status.get('status', '')
                print(f"  Status: {s}")
                if s == 'completed':
                    print("\nDone! Layer is ready.")
                    break
                elif s == 'failed':
                    raise Exception(f"Publish failed: {status}")
                time.sleep(2)
    else:
        print(f"Publish response: {pub_result}")

if __name__ == "__main__":
    main()
