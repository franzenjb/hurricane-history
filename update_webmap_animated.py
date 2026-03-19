"""
Update hurricane web map with CIM vector symbols that have
built-in flow animation (offset animation along the line).
"""

import urllib.request
import urllib.parse
import json

AGOL_BASE = "https://franzengiscorp.maps.arcgis.com"
USERNAME = "jefffranzen_giscorp"
MAP_ITEM_ID = "eaa297ba11714e1c896514d5f4b16ed1"

SVC_BASE = "https://services7.arcgis.com/1J4A0YH8gSNAmQVQ/arcgis/rest/services"
SEGMENTS_URL = f"{SVC_BASE}/Atlantic_Hurricane_Track_Segments_1851_2025/FeatureServer/0"
POINTS_URL = f"{SVC_BASE}/Atlantic_Hurricane_Tracks_1851_2025/FeatureServer/0"
TABLE_URL = f"{SVC_BASE}/Atlantic_Hurricanes_1851_2025/FeatureServer/0"

SEGMENTS_ITEM = "a4fac5e27f5d4ba3befad81a7eb8a056"
POINTS_ITEM = "a62e3d140b614ced8509168434a0d90e"
TABLE_ITEM = "08a82646b8fc45d691fd9524b4b6d36c"

# Category colors [R, G, B, A]
CAT_COLORS = {
    -1: [120, 120, 120, 160],
    0:  [21, 101, 192, 200],
    1:  [0, 105, 92, 220],
    2:  [230, 81, 0, 220],
    3:  [216, 67, 21, 240],
    4:  [183, 28, 28, 245],
    5:  [127, 0, 0, 255],
}

# Arrow marker colors (slightly lighter for visibility)
ARROW_COLORS = {
    -1: [180, 180, 180, 200],
    0:  [100, 160, 230, 230],
    1:  [0, 170, 150, 240],
    2:  [255, 140, 40, 240],
    3:  [240, 110, 60, 250],
    4:  [220, 60, 60, 250],
    5:  [180, 30, 30, 255],
}

WIDTHS = {-1: 0.75, 0: 1.0, 1: 1.5, 2: 2.0, 3: 2.75, 4: 3.5, 5: 4.5}

LABELS = {
    -1: "Tropical Depression", 0: "Tropical Storm",
    1: "Category 1", 2: "Category 2",
    3: "Category 3 (Major)", 4: "Category 4 (Major)", 5: "Category 5 (Major)",
}

def build_animated_cim_line(cat_num):
    """Build a CIM line symbol with animated directional arrows."""
    color = CAT_COLORS[cat_num]
    arrow_color = ARROW_COLORS[cat_num]
    width = WIDTHS[cat_num]
    arrow_size = max(4, width * 2.5)
    spacing = max(12, 30 - cat_num * 3)

    return {
        "type": "CIMSymbolReference",
        "symbol": {
            "type": "CIMLineSymbol",
            "symbolLayers": [
                # Base stroke
                {
                    "type": "CIMSolidStroke",
                    "enable": True,
                    "width": width,
                    "color": color,
                    "capStyle": "Round",
                    "joinStyle": "Round",
                },
                # Animated directional arrows along the line
                {
                    "type": "CIMVectorMarker",
                    "enable": True,
                    "size": arrow_size,
                    "markerPlacement": {
                        "type": "CIMMarkerPlacementAlongLineSameSize",
                        "endings": "WithMarkers",
                        "placementTemplate": [spacing],
                        "angleToLine": True,
                    },
                    "frame": {
                        "xmin": -5,
                        "ymin": -5,
                        "xmax": 5,
                        "ymax": 5,
                    },
                    "markerGraphics": [
                        {
                            "type": "CIMMarkerGraphic",
                            "geometry": {
                                "rings": [[[-4, -3.5], [-4, 3.5], [3, 0], [-4, -3.5]]]
                            },
                            "symbol": {
                                "type": "CIMPolygonSymbol",
                                "symbolLayers": [
                                    {
                                        "type": "CIMSolidFill",
                                        "enable": True,
                                        "color": arrow_color,
                                    }
                                ]
                            }
                        }
                    ],
                    "primitiveName": "arrowMarker",
                },
            ],
            "animations": [
                {
                    "type": "CIMSymbolAnimationOffset",
                    "primitiveName": "arrowMarker",
                    "xOffset": spacing,
                    "yOffset": 0,
                    "animatedSymbolProperties": {
                        "type": "CIMAnimatedSymbolProperties",
                        "primitiveName": "arrowMarker",
                        "playAnimation": True,
                        "randomizeStartTime": True,
                        "repeatType": "Loop",
                        "repeatDelay": 0,
                        "duration": 2.0,
                    }
                }
            ],
        }
    }


def build_animated_renderer():
    """Unique value renderer with CIM animated symbols."""
    infos = []
    for cat_num in [-1, 0, 1, 2, 3, 4, 5]:
        infos.append({
            "value": str(cat_num),
            "label": LABELS[cat_num],
            "symbol": build_animated_cim_line(cat_num),
        })

    return {
        "type": "uniqueValue",
        "field1": "category_num",
        "defaultSymbol": build_animated_cim_line(-1),
        "defaultLabel": "Other",
        "uniqueValueInfos": infos,
    }


def build_landfall_renderer():
    infos = []
    for cat in [1, 2, 3, 4, 5]:
        size = 5 + cat * 2.5
        infos.append({
            "value": str(cat),
            "label": LABELS[cat],
            "symbol": {
                "type": "esriSMS",
                "style": "esriSMSDiamond",
                "color": CAT_COLORS[cat],
                "size": size,
                "outline": {"color": [255, 255, 255, 220], "width": 1.25},
            }
        })
    return {
        "type": "uniqueValue",
        "field1": "category_num",
        "defaultSymbol": {
            "type": "esriSMS",
            "style": "esriSMSDiamond",
            "color": [100, 100, 100, 180],
            "size": 5,
            "outline": {"color": [255, 255, 255, 200], "width": 1},
        },
        "defaultLabel": "Other",
        "uniqueValueInfos": infos,
    }


def get_token():
    with open('/tmp/giscorps_token.txt', 'r') as f:
        return f.read().strip()


def main():
    token = get_token()

    # Read arcade popups
    with open("segment_popup.arcade", "r") as f:
        segment_arcade = f.read()

    landfall_arcade = r'''
var nm = DefaultValue($feature.name, "UNNAMED")
var yr = $feature.year
var dt = DefaultValue($feature.datetime, "")
var catNum = DefaultValue($feature.category_num, -1)
var cat = DefaultValue($feature.category, "Unknown")
var windKt = DefaultValue($feature.wind_kt, 0)
var windMph = DefaultValue($feature.wind_mph, 0)
var presMb = DefaultValue($feature.pressure_mb, 0)
var headerBg = IIF(catNum >= 5, "#7f0000", IIF(catNum >= 4, "#b71c1c", IIF(catNum >= 3, "#d84315", IIF(catNum >= 2, "#e65100", IIF(catNum >= 1, "#00695c", "#1565C0")))))
var windClr = headerBg
var windKtF = Text(windKt, "#,###")
var windMphF = Text(windMph, "#,###")
var presF = IIF(presMb > 0 && presMb < 9999, Text(presMb, "#,###") + " mb", "N/A")
var windBarW = IIF(windKt > 0, Min(Round((windKt / 170) * 100, 0), 100), 0)
return {
  type: "text",
  text:
'<div style="font-family:Arial,Helvetica,sans-serif;max-width:320px;color:#1a1a1a;line-height:1.4;">' +
'<div style="background:' + headerBg + ';padding:14px 16px;margin:-8px -8px 0 -8px;border-radius:4px 4px 0 0;">' +
  '<div style="font-size:11px;color:rgba(255,255,255,0.8);text-transform:uppercase;letter-spacing:1px;font-weight:700;">Landfall</div>' +
  '<div style="font-size:22px;font-weight:700;color:#fff;margin-top:2px;">' + nm + '</div>' +
  '<div style="margin-top:8px;display:flex;align-items:center;">' +
    '<span style="display:inline-block;padding:4px 12px;border-radius:12px;background:rgba(255,255,255,0.2);border:1px solid rgba(255,255,255,0.4);font-size:12px;font-weight:700;color:#fff;">' + Upper(cat) + '</span>' +
    '<span style="margin-left:10px;font-size:13px;color:rgba(255,255,255,0.9);">' + Text(yr, "####") + '</span>' +
  '</div>' +
'</div>' +
'<div style="display:flex;justify-content:space-between;padding:12px 16px;background:#f0f0f0;border-bottom:1px solid #ccc;">' +
  '<div style="text-align:center;flex:1;">' +
    '<div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">Wind</div>' +
    '<div style="font-size:18px;font-weight:700;color:' + windClr + ';">' + windKtF + ' kt</div>' +
    '<div style="font-size:11px;color:#555;">' + windMphF + ' mph</div>' +
  '</div>' +
  '<div style="text-align:center;flex:1;border-left:1px solid #ccc;">' +
    '<div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:0.5px;font-weight:600;">Pressure</div>' +
    '<div style="font-size:18px;font-weight:700;color:#1a1a1a;">' + presF + '</div>' +
  '</div>' +
'</div>' +
'<div style="padding:12px 16px;">' +
  '<div style="font-size:11px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px;">Landfall Intensity</div>' +
  '<div style="background:#ddd;border-radius:4px;height:16px;overflow:hidden;position:relative;">' +
    '<div style="background:' + windClr + ';width:' + windBarW + '%;height:100%;border-radius:4px;min-width:24px;"></div>' +
    '<span style="position:absolute;top:1px;left:6px;font-size:10px;font-weight:700;color:#fff;">' + windKtF + ' kt</span>' +
  '</div>' +
  '<div style="font-size:13px;color:#444;margin-top:8px;">' + dt + '</div>' +
'</div>' +
'<div style="padding:6px 16px 10px 16px;border-top:1px solid #ccc;">' +
  '<div style="font-size:10px;color:#666;">NOAA NHC HURDAT2</div>' +
'</div>' +
'</div>'
}
'''

    webmap = {
        "operationalLayers": [
            {
                "id": "landfall_points",
                "title": "Landfall Points",
                "url": POINTS_URL,
                "itemId": POINTS_ITEM,
                "layerType": "ArcGISFeatureLayer",
                "visibility": True,
                "opacity": 0.95,
                "minScale": 18000000,
                "definitionExpression": "is_landfall = 1 AND is_major = 1",
                "layerDefinition": {
                    "drawingInfo": {
                        "renderer": build_landfall_renderer(),
                    },
                    "definitionExpression": "is_landfall = 1 AND is_major = 1",
                    "minScale": 18000000,
                },
                "popupInfo": {
                    "title": "Landfall: {name} ({year})",
                    "expressionInfos": [{
                        "name": "landfall_popup",
                        "title": "Landfall Details",
                        "expression": landfall_arcade,
                        "returnType": "dictionary",
                    }],
                    "popupElements": [{
                        "type": "expression",
                        "expressionInfoId": "landfall_popup",
                    }],
                },
            },
            {
                "id": "track_segments",
                "title": "Storm Track Segments",
                "url": SEGMENTS_URL,
                "itemId": SEGMENTS_ITEM,
                "layerType": "ArcGISFeatureLayer",
                "visibility": True,
                "opacity": 0.85,
                "definitionExpression": "peak_category_num >= 3",
                "layerDefinition": {
                    "drawingInfo": {
                        "renderer": build_animated_renderer(),
                    },
                    "definitionExpression": "peak_category_num >= 3",
                },
                "popupInfo": {
                    "title": "{name} ({year})",
                    "expressionInfos": [{
                        "name": "segment_popup",
                        "title": "Storm Details",
                        "expression": segment_arcade,
                        "returnType": "dictionary",
                    }],
                    "popupElements": [{
                        "type": "expression",
                        "expressionInfoId": "segment_popup",
                    }],
                },
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
                    "popupElements": [{"type": "fields"}],
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
                    "xmin": -110,
                    "ymin": 8,
                    "xmax": -20,
                    "ymax": 50,
                    "spatialReference": {"wkid": 4326}
                }
            }
        },
        "version": "2.31",
        "authoringApp": "ArcGISMapViewer",
        "authoringAppVersion": "2024.3",
    }

    update_url = f"{AGOL_BASE}/sharing/rest/content/users/{USERNAME}/items/{MAP_ITEM_ID}/update"
    data = urllib.parse.urlencode({
        'f': 'json',
        'token': token,
        'text': json.dumps(webmap),
    }).encode()

    req = urllib.request.Request(update_url, data=data)
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode())

    if not result.get('success'):
        raise Exception(f"Update failed: {result}")

    print(f"Web map updated with CIM animated symbols!")
    print(f"Open: {AGOL_BASE}/apps/mapviewer/index.html?webmap={MAP_ITEM_ID}")

if __name__ == "__main__":
    main()
