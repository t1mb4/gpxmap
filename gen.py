#!venv/bin/python
import os
import gpxpy
import re
import json
import argparse
import sys
import gzip

GPX_DIR = 'tracks'
OUTPUT_HYBRIDMAP_HTML = 'index.html'

POINT_SKIP = 5  # take every Nth point to simplify tracks

def clean_gpx_namespaces(gpx_content):
    """Remove XML namespaces and prefixes for easier parsing"""
    cleaned = re.sub(r'\s+xmlns:[^\s=]+="[^"]+"', '', gpx_content)
    cleaned = re.sub(r'\b\w+?:', '', cleaned)
    return cleaned

def parse_gpx_file(file_path):
    """Parse a GPX file and extract track points and named waypoints"""
    try:
        with open(file_path, 'r') as gpx_file:
            gpx_content = gpx_file.read()
            gpx_content = clean_gpx_namespaces(gpx_content)
            gpx = gpxpy.parse(gpx_content)
            tracks = []
            all_points = []
            named_points = []

            for track in gpx.tracks:
                for segment in track.segments:
                    points = [(p.latitude, p.longitude) for p in segment.points]
                    if points:
                        simplified = points[::POINT_SKIP] if POINT_SKIP > 1 else points
                        tracks.append((simplified, os.path.basename(file_path)))
                        all_points.extend(simplified)

            for wpt in gpx.waypoints:
                if wpt.name:
                    named_points.append((wpt.latitude, wpt.longitude, wpt.name, os.path.basename(file_path)))

            return tracks, all_points, named_points

    except Exception as e:
        print(f"[!] Error parsing {file_path}: {e}")
        return [], [], []

def save_geodata(tracks, all_points, named_points):
    print("[*] Saving geodata to geo_data.json...")

    tracks_data = [{"filename": f, "coords": pts} for pts, f in tracks]
    heat_points = all_points
    named_data = [
        {"lat": lat, "lon": lon, "name": name, "filename": filename}
        for lat, lon, name, filename in named_points
    ]

    geo_data = {
        "tracks": tracks_data,
        "heat_points": heat_points,
        "named_points": named_data
    }

    with gzip.open("geo_data.json.gz", "wt", encoding="utf-8") as gz:
        json.dump(geo_data, gz)

    print("[+] geo_data.json and geo_data.json.gz saved")

def generate_hybridmap_html():
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>GPXMAP</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet.locatecontrol/dist/L.Control.Locate.min.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        #map { height: 100vh; margin: 0; }

        .leaflet-control-layers { margin: 0; }

        .leaflet-control-layers-overlays label {
            font-size: 18px;
            line-height: 34px;
        }

        .leaflet-control-layers-overlays input[type="checkbox"] {
            position: absolute;
            opacity: 0;
            cursor: pointer;
            height: 0;
            width: 0;
        }

        .leaflet-control-layers-overlays .switch {
            position: relative;
            display: inline-block;
            width: 52px;
            height: 28px;
            margin-right: 10px;
        }

        .leaflet-control-layers-overlays .slider {
            position: absolute;
            cursor: pointer;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 34px;
        }

        .leaflet-control-layers-overlays .slider:before {
            position: absolute;
            content: "";
            height: 20px;
            width: 20px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }

        .leaflet-control-layers-overlays input:checked + .slider {
            background-color: #2196F3;
        }

        .leaflet-control-layers-overlays input:checked + .slider:before {
            transform: translateX(24px);
        }

        .leaflet-control-locate a {
            width: 60px !important;
            height: 60px !important;
            font-size: 28px !important;
            line-height: 60px !important;
        }

        .leaflet-bottom.leaflet-left {
            bottom: 90px !important;
            left: 10px;
        }

        .leaflet-bottom.leaflet-right {
            bottom: 90px !important;
            right: 10px;
        }

        .leaflet-control-layers {
            max-height: 240px;
            overflow-y: auto;
        }

        .leaflet-control-zoom a {
            width: 70px;
            height: 70px;
            line-height: 60px;
            font-size: 34px;
        }

        .leaflet-control-custom {
            margin-top: 10px;
        }

        @media (max-width: 768px) {
            .leaflet-control-custom {
                margin-top: 60px;
            }
            .leaflet-control-zoom {
                margin-top: 60px;
            }
        }
        #loader {
            position: fixed;
            z-index: 1000;
            top: 0; left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255,255,255,0.9);
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .loader-spinner {
            border: 12px solid #f3f3f3;
            border-top: 12px solid #3498db;
            border-radius: 50%;
            width: 80px;
            height: 80px;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0%   { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
<div id="loader">
    <div class="loader-spinner"></div>
</div>
<div id="map"></div>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>
<script src="https://unpkg.com/leaflet.locatecontrol/dist/L.Control.Locate.min.js"></script>
<script>
var map = L.map('map').setView([48.5, 31], 6);

var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(map);
var esriLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18 });

var currentBaseLayer = osmLayer;

var baseMapsControl = L.control({position: 'topright'});
baseMapsControl.onAdd = function (map) {
  var div = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-custom');
  div.innerHTML = `
    <select id="basemap-select" style="font-size:16px; padding:6px; border:none; background:white; border-radius:4px;">
      <option value="osm">OSM</option>
      <option value="esri">ArcGIS Aerial</option>
    </select>
  `;
  L.DomEvent.disableClickPropagation(div);
  return div;
};
baseMapsControl.addTo(map);

document.getElementById('basemap-select').addEventListener('change', function(e) {
  map.removeLayer(currentBaseLayer);
  if (e.target.value === 'osm') {
    currentBaseLayer = osmLayer;
  } else {
    currentBaseLayer = esriLayer;
  }
  map.addLayer(currentBaseLayer);
});

var blueIcon = L.icon({iconUrl:'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png', iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png', shadowSize:[41,41]});
var greenIcon = L.icon({iconUrl:'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png', iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png', shadowSize:[41,41]});
var yellowIcon = L.icon({iconUrl:'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-yellow.png', iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png', shadowSize:[41,41]});
var redIcon = L.icon({iconUrl:'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png', iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png', shadowSize:[41,41]});

var tracksLayer = L.layerGroup();
var heatLayerGroup = L.layerGroup();
var todoMarkersLayer = L.layerGroup();
var otherMarkersLayer = L.layerGroup();
var dsLayer = L.layerGroup();


document.getElementById('loader').style.display = 'flex';

const basePath = new URL('./', window.location.href).href;
const geoDataUrl = basePath + 'geo_data.json.gz';


fetch(geoDataUrl)
  .then(response => response.json())
  .then(data => {
    data.tracks.forEach(track => {
      L.polyline(track.coords, { color: '#ff0000', weight: 3 })
        .bindPopup("<small style='font-size:10px'>" + track.filename + "</small>")
        .addTo(tracksLayer);
    });

    L.heatLayer(data.heat_points, { radius: 12, blur: 15, maxZoom: 17 }).addTo(heatLayerGroup);

    data.named_points.forEach(pt => {
      var iconVar = pt.filename.includes("TODO_MAIN") ? greenIcon :
                    pt.filename.includes("WP_WAR_RB") ? redIcon :
                    pt.filename.includes("WP_") ? blueIcon : yellowIcon;
      var marker = L.marker([pt.lat, pt.lon], {icon: iconVar})
        .bindPopup(
          "<b>" + pt.name + "</b><br>" +
          "<small>" + pt.lat.toFixed(6) + ", " + pt.lon.toFixed(6) + "<br>" +
          pt.filename + "</small>"
        );
      if (pt.filename.includes("TODO")) {
        marker.addTo(todoMarkersLayer);
      } else {
        marker.addTo(otherMarkersLayer);
      }
    });
  });

fetch(basePath + 'deepstate.geojson')
    .then(res => res.json())
    .then(ds => {
      L.geoJson(ds, {
        style: { color: '#ff0000', weight: 2, fillOpacity: 0.2 }
      }).addTo(dsLayer);
    })
  .finally(() => {
    document.getElementById('loader').style.display = 'none';
  });

var overlays = {
  "Tracks": tracksLayer,
  "Heatmap": heatLayerGroup,
  "POI": otherMarkersLayer,
  "POI: TODO": todoMarkersLayer,
  "DeepState": dsLayer
};
L.control.layers(null, overlays, {collapsed: false, position: 'bottomright'}).addTo(map);

L.control.locate({
  position: 'bottomleft',
  flyTo: true,
  strings: { title: "My location" },
  locateOptions: { enableHighAccuracy: true },
  icon: 'fa fa-crosshairs'
}).addTo(map);

setTimeout(() => {
  document.querySelectorAll('.leaflet-control-layers-overlays label').forEach(label => {
    var input = label.querySelector('input[type="checkbox"]');
    if (input) {
      var wrapper = document.createElement('label');
      wrapper.classList.add('switch');

      var slider = document.createElement('span');
      slider.classList.add('slider');

      input.parentNode.insertBefore(wrapper, input);
      wrapper.appendChild(input);
      wrapper.appendChild(slider);

      label.insertBefore(wrapper, label.firstChild);
    }
  });
}, 300);
</script>
</body>
</html>"""
    return html



def main(gen_geodata=False, gen_html=False):

    if gen_geodata:
        all_tracks, all_points, all_named_points = [], [], []
        for root, _, files in os.walk(GPX_DIR, followlinks=True):
            for filename in files:
                if filename.lower().endswith('.gpx'):
                    file_path = os.path.join(root, filename)
                    print(f"[*] Processing {file_path}")
                    tracks, points, named_points = parse_gpx_file(file_path)
                    all_tracks.extend(tracks)
                    all_points.extend(points)
                    all_named_points.extend(named_points)
    
        print(f"[+] Total points for heatmap: {len(all_points)}")
        print(f"[+] Total named waypoints: {len(all_named_points)}")
        if not all_tracks:
            print("[!] No tracks found. Exiting.")
            return
        save_geodata(all_tracks, all_points, all_named_points)

    if gen_html:
        with open(OUTPUT_HYBRIDMAP_HTML, 'w') as f:
            f.write(generate_hybridmap_html())
        print(f"[+] Hybrid map saved to {OUTPUT_HYBRIDMAP_HTML}")
    else:
        print("[*] HTML generation skipped.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GPX processor script")
    parser.add_argument('--geodata', action='store_true', help='Generate geodata files')
    parser.add_argument('--html', action='store_true', help='Generate HTML files')

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(0)

    main(gen_geodata=args.geodata, gen_html=args.html)
