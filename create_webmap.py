"""
Create a web map with hurricane track segments styled by intensity,
symbol animation enabled, summary table, and landfall points.
"""

import urllib.request
import urllib.parse
import json
import time

AGOL_BASE = "https://franzengiscorp.maps.arcgis.com"
USERNAME = "jefffranzen_giscorp"
SVC_BASE = "https://services7.arcgis.com/1J4A0YH8gSNAmQVQ/arcgis/rest/services"

# Layer URLs
SEGMENTS_URL = f"{SVC_BASE}/Atlantic_Hurricane_Track_Segments_1851_2025/FeatureServer/0"
POINTS_URL = f"{SVC_BASE}/Atlantic_Hurricane_Tracks_1851_2025/FeatureServer/0"
TABLE_URL = f"{SVC_BASE}/Atlantic_Hurricanes_1851_2025/FeatureServer/0"

# Item IDs
SEGMENTS_ITEM = "a4fac5e27f5d4ba3befad81a7eb8a056"
POINTS_ITEM = "a62e3d140b614ced8509168434a0d90e"
TABLE_ITEM = "08a82646b8fc45d691fd9524b4b6d36c"

# NHC-style color scheme (RGB)
COLORS = {
    -1: [180, 180, 180, 180],   # TD - gray
    0:  [0, 154, 255, 200],     # TS - blue
    1:  [0, 200, 200, 220],     # Cat 1 - cyan
    2:  [255, 255, 0, 220],     # Cat 2 - yellow
    3:  [255, 165, 0, 230],     # Cat 3 - orange
    4:  [255, 69, 0, 240],      # Cat 4 - red-orange
    5:  [200, 0, 0, 255],       # Cat 5 - deep red
}

WIDTHS = {
    -1: 0.75,  # TD
    0:  1.0,   # TS
    1:  1.5,   # Cat 1
    2:  2.0,   # Cat 2
    3:  2.75,  # Cat 3
    4:  3.5,   # Cat 4
    5:  4.5,   # Cat 5
}

LABELS = {
    -1: "Tropical Depression",
    0:  "Tropical Storm",
    1:  "Category 1",
    2:  "Category 2",
    3:  "Category 3 (Major)",
    4:  "Category 4 (Major)",
    5:  "Category 5 (Major)",
}

def get_token():
    with open('/tmp/giscorps_token.txt', 'r') as f:
        return f.read().strip()

def build_unique_value_infos():
    """Build renderer unique value entries for each category."""
    infos = []
    for cat_num in [-1, 0, 1, 2, 3, 4, 5]:
        infos.append({
            "value": str(cat_num),
            "label": LABELS[cat_num],
            "symbol": {
                "type": "esriSLS",
                "style": "esriSLSSolid",
                "color": COLORS[cat_num],
                "width": WIDTHS[cat_num],
            }
        })
    return infos

def build_segments_renderer():
    return {
        "type": "uniqueValue",
        "field1": "category_num",
        "defaultSymbol": {
            "type": "esriSLS",
            "style": "esriSLSSolid",
            "color": [128, 128, 128, 150],
            "width": 0.5,
        },
        "defaultLabel": "Other",
        "uniqueValueInfos": build_unique_value_infos(),
    }

def build_segments_popup():
    return {
        "title": "{name} ({year})",
        "fieldInfos": [
            {"fieldName": "storm_id", "label": "Storm ID", "visible": True},
            {"fieldName": "name", "label": "Name", "visible": True},
            {"fieldName": "year", "label": "Year", "visible": True},
            {"fieldName": "datetime", "label": "Date/Time", "visible": True},
            {"fieldName": "category", "label": "Category", "visible": True},
            {"fieldName": "wind_kt", "label": "Wind (kt)", "visible": True},
            {"fieldName": "wind_mph", "label": "Wind (mph)", "visible": True},
            {"fieldName": "pressure_mb", "label": "Pressure (mb)", "visible": True},
            {"fieldName": "peak_category", "label": "Storm Peak Category", "visible": True},
            {"fieldName": "is_landfall", "label": "Landfall Segment", "visible": True},
        ],
        "popupElements": [
            {
                "type": "fields",
            }
        ],
    }

def build_landfall_renderer():
    """Landfall points — red diamonds sized by category."""
    return {
        "type": "uniqueValue",
        "field1": "category_num",
        "defaultSymbol": {
            "type": "esriSMS",
            "style": "esriSMSDiamond",
            "color": [255, 0, 0, 200],
            "size": 6,
            "outline": {"color": [255, 255, 255, 255], "width": 1},
        },
        "defaultLabel": "Other",
        "uniqueValueInfos": [
            {
                "value": str(cat),
                "label": LABELS[cat],
                "symbol": {
                    "type": "esriSMS",
                    "style": "esriSMSDiamond",
                    "color": COLORS[cat],
                    "size": max(6, 4 + cat * 2.5),
                    "outline": {"color": [50, 50, 50, 255], "width": 1},
                }
            }
            for cat in [-1, 0, 1, 2, 3, 4, 5]
        ],
    }

def build_landfall_popup():
    return {
        "title": "Landfall: {name} ({year})",
        "fieldInfos": [
            {"fieldName": "name", "label": "Storm", "visible": True},
            {"fieldName": "year", "label": "Year", "visible": True},
            {"fieldName": "datetime", "label": "Landfall Time", "visible": True},
            {"fieldName": "category", "label": "Category at Landfall", "visible": True},
            {"fieldName": "wind_kt", "label": "Wind (kt)", "visible": True},
            {"fieldName": "wind_mph", "label": "Wind (mph)", "visible": True},
            {"fieldName": "pressure_mb", "label": "Pressure (mb)", "visible": True},
        ],
        "popupElements": [{"type": "fields"}],
    }

def main():
    token = get_token()

    webmap = {
        "operationalLayers": [
            # Landfall points (on top)
            {
                "id": "landfall_points",
                "title": "Landfall Points",
                "url": POINTS_URL,
                "itemId": POINTS_ITEM,
                "layerType": "ArcGISFeatureLayer",
                "visibility": True,
                "opacity": 0.9,
                "definitionExpression": "is_landfall = 1",
                "layerDefinition": {
                    "drawingInfo": {
                        "renderer": build_landfall_renderer(),
                    },
                    "definitionExpression": "is_landfall = 1",
                },
                "popupInfo": build_landfall_popup(),
            },
            # Track segments (main layer)
            {
                "id": "track_segments",
                "title": "Storm Track Segments",
                "url": SEGMENTS_URL,
                "itemId": SEGMENTS_ITEM,
                "layerType": "ArcGISFeatureLayer",
                "visibility": True,
                "opacity": 0.85,
                "layerDefinition": {
                    "drawingInfo": {
                        "renderer": build_segments_renderer(),
                        "symbolAnimation": {
                            "enabled": True,
                            "type": "flow",
                            "speed": 1.0,
                        },
                    },
                },
                "popupInfo": build_segments_popup(),
            },
        ],
        "tables": [
            {
                "id": "storm_summary",
                "title": "Storm Summary (1851-2025)",
                "url": TABLE_URL,
                "itemId": TABLE_ITEM,
                "layerType": "ArcGISFeatureLayer",
                "popupInfo": {
                    "title": "{name} ({year})",
                    "fieldInfos": [
                        {"fieldName": "name", "label": "Name", "visible": True},
                        {"fieldName": "year", "label": "Year", "visible": True},
                        {"fieldName": "month_name", "label": "Month", "visible": True},
                        {"fieldName": "category", "label": "Peak Category", "visible": True},
                        {"fieldName": "max_wind_kt", "label": "Max Wind (kt)", "visible": True},
                        {"fieldName": "max_wind_mph", "label": "Max Wind (mph)", "visible": True},
                        {"fieldName": "min_pressure_mb", "label": "Min Pressure (mb)", "visible": True},
                        {"fieldName": "duration_hours", "label": "Duration (hrs)", "visible": True},
                        {"fieldName": "landfalls", "label": "Landfalls", "visible": True},
                        {"fieldName": "start_date", "label": "Start Date", "visible": True},
                        {"fieldName": "end_date", "label": "End Date", "visible": True},
                    ],
                    "popupElements": [{"type": "fields"}],
                },
            },
        ],
        "baseMap": {
            "baseMapLayers": [
                {
                    "id": "dark_gray_base",
                    "title": "Dark Gray Canvas",
                    "layerType": "ArcGISTiledMapServiceLayer",
                    "url": "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Base/MapServer",
                    "visibility": True,
                    "opacity": 1,
                },
                {
                    "id": "dark_gray_ref",
                    "title": "Dark Gray Reference",
                    "layerType": "ArcGISTiledMapServiceLayer",
                    "url": "https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Reference/MapServer",
                    "visibility": True,
                    "opacity": 1,
                    "isReference": True,
                },
            ],
            "title": "Dark Gray Canvas",
        },
        "spatialReference": {"wkid": 102100, "latestWkid": 3857},
        "initialState": {
            "viewpoint": {
                "targetGeometry": {
                    "xmin": -120,
                    "ymin": 5,
                    "xmax": -10,
                    "ymax": 55,
                    "spatialReference": {"wkid": 4326}
                }
            }
        },
        "version": "2.31",
        "authoringApp": "ArcGISMapViewer",
        "authoringAppVersion": "2024.3",
    }

    # Create the web map item
    add_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/addItem"
    data = urllib.parse.urlencode({
        'f': 'json',
        'token': token,
        'type': 'Web Map',
        'title': 'Atlantic Hurricane Tracks 1851-2025',
        'tags': 'hurricanes,NOAA,HURDAT2,Atlantic,weather,disasters,NHC,animated,tracks',
        'description': (
            '<b>174 years of Atlantic hurricane history</b> — every storm track from 1851 to 2025.<br><br>'
            '<b>Track Segments:</b> 53,601 polyline segments colored by Saffir-Simpson intensity. '
            'Lines shift from gray (TD) → blue (TS) → cyan/yellow/orange/red (Cat 1-5) '
            'as storms strengthen and weaken along their path. Symbol animation shows flow direction.<br><br>'
            '<b>Landfall Points:</b> 1,175 diamond markers at exact landfall locations, '
            'sized and colored by intensity at landfall.<br><br>'
            '<b>Summary Table:</b> 2,004 storms with peak category, max wind, pressure, duration, '
            'and landfall count. Use for Calendar Heat Charts by start_date.<br><br>'
            'Source: NOAA National Hurricane Center HURDAT2 database.'
        ),
        'snippet': 'Animated hurricane tracks 1851-2025 — 53K segments colored by intensity, 1,175 landfall points, 2,004 storm summaries',
        'text': json.dumps(webmap),
        'extent': '-120,5,-10,55',
    }).encode()

    req = urllib.request.Request(add_url, data=data)
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode())

    if not result.get('success'):
        raise Exception(f"Failed: {result}")

    map_id = result['id']
    print(f"Web map created!")
    print(f"  Item ID: {map_id}")
    print(f"  View: {AGOL_BASE}/home/item.html?id={map_id}")
    print(f"  Open in Map Viewer: {AGOL_BASE}/apps/mapviewer/index.html?webmap={map_id}")
    print(f"\n--- NEXT STEPS in Map Viewer ---")
    print(f"  1. Open the map in Map Viewer")
    print(f"  2. Click Storm Track Segments layer → Styles")
    print(f"  3. Verify unique values by category_num are showing")
    print(f"  4. Click the animation icon (new Feb 2026) on the line symbols")
    print(f"  5. Enable flow animation → adjust speed")
    print(f"  6. Add a Calendar Heat Chart from the Summary Table (start_date, monthly)")
    print(f"  7. Save")

if __name__ == "__main__":
    main()
