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

POINT_SKIP = 5

def clean_gpx_namespaces(gpx_content):
    cleaned = re.sub(r'\s+xmlns:[^\s=]+="[^"]+"', '', gpx_content)
    cleaned = re.sub(r'\b\w+?:', '', cleaned)
    return cleaned

def parse_gpx_file(file_path):
    try:
        with open(file_path, 'r') as gpx_file:
            gpx_content = gpx_file.read()
            gpx_content = clean_gpx_namespaces(gpx_content)
            gpx = gpxpy.parse(gpx_content)
            segments = []
            all_coords = []
            for track in gpx.tracks:
                for segment in track.segments:
                    points = [(p.latitude, p.longitude) for p in segment.points]
                    if points:
                        simplified = points[::POINT_SKIP] if POINT_SKIP > 1 else points
                        segments.append(simplified)
                        all_coords.extend(simplified)
            named_points = []
            for wpt in gpx.waypoints:
                if wpt.name:
                    named_points.append((wpt.latitude, wpt.longitude, wpt.name, os.path.basename(file_path)))
            return {
                "filename": os.path.basename(file_path),
                "coords": all_coords,
                "segments": segments
            }, all_coords, named_points
    except Exception as e:
        print(f"[!] Error parsing {file_path}: {e}")
        return None, [], []

def save_geodata(tracks, all_points, named_points):
    print("[*] Saving geodata to geo_data.json...")
    tracks_data = [t for t in tracks if t is not None]
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
    geo_data_mtime = int(os.path.getmtime('geo_data.json.gz'))
    deepstate_mtime = int(os.path.getmtime('deepstate.geojson'))
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
<div id="track-progressbar-container" style="position:fixed;left:0;right:0;bottom:30px;height:32px;display:none;z-index:1001;pointer-events:auto;">
  <div id="track-progressbar" style="width:90%;margin:0 auto;background:#eee;height:16px;border-radius:8px;position:relative;top:8px;cursor:pointer; border:2px solid #333; box-shadow:0 1px 8px rgba(0,0,0,0.15);">
    <div id="track-progressbar-fill" style="background:#00ff00;width:0%;height:100%;border-radius:8px;"></div>
    <div id="track-progressbar-hoverdot" style="position:absolute;top:50%;left:0;width:16px;height:16px;background:#00ff00;border-radius:50%;transform:translate(-50%,-50%);display:none;pointer-events:none;"></div>
    <div id="track-progressbar-distlabel" style="position:absolute;top:-28px;left:0;transform:translateX(-50%);background:#fff;padding:2px 6px;border-radius:6px;font-size:13px;border:1px solid #333;display:none;white-space:nowrap;z-index:10;box-shadow:0 1px 4px rgba(0,0,0,0.12);"></div>
    <div id="track-progressbar-totaldist" style="position:absolute;top:22px;right:0;font-size:13px;color:#222;background:#fff;padding:2px 8px;border-radius:6px;border:1px solid #333;box-shadow:0 1px 4px rgba(0,0,0,0.10);"></div>
  </div>
</div>

<script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>
<script src="https://unpkg.com/leaflet.locatecontrol/dist/L.Control.Locate.min.js"></script>
<script>
function getUrlParams() {
    const params = {};
    window.location.search.substring(1).split("&").forEach(function(part) {
        if (!part) return;
        let item = part.split("=");
        let key = decodeURIComponent(item[0]);
        let value = decodeURIComponent(item[1] || "");
        params[key] = value;
    });
    return params;
}
function setUrlParams(params) {
    const search = Object.entries(params)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join("&");
    history.replaceState(null, '', '?' + search);
}
const params = getUrlParams();
let mapLat = params.lat ? parseFloat(params.lat) : 44.350127;
let mapLng = params.lng ? parseFloat(params.lng) : 30.944312;
let mapZoom = params.zoom ? parseInt(params.zoom) : 5;
let baseLayerName = params.base || 'osm';
let activeLayers = params.layers ? params.layers.split(',') : [];
var map = L.map('map').setView([mapLat, mapLng], mapZoom);
var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 });
var esriLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18 });
var currentBaseLayer = baseLayerName === 'esri' ? esriLayer : osmLayer;
map.addLayer(currentBaseLayer);
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
document.getElementById('basemap-select').value = baseLayerName;
document.getElementById('basemap-select').addEventListener('change', function(e) {
  map.removeLayer(currentBaseLayer);
  if (e.target.value === 'osm') {
    currentBaseLayer = osmLayer;
  } else {
    currentBaseLayer = esriLayer;
  }
  map.addLayer(currentBaseLayer);
  updateUrl();
});
var blueIcon = L.icon({iconUrl:'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png', iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'});
var greenIcon = L.icon({iconUrl:'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png', iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'});
var yellowIcon = L.icon({iconUrl:'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-yellow.png', iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'});
var redIcon = L.icon({iconUrl:'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png', iconSize:[25,41], iconAnchor:[12,41], popupAnchor:[1,-34], shadowUrl:'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png'});
var tracksLayer = L.layerGroup();
var heatLayerGroup = L.layerGroup();
var todoMarkersLayer = L.layerGroup();
var otherMarkersLayer = L.layerGroup();
var dsLayer = L.layerGroup();
var selectedTrackFilename = null;
var selectedTrackOpts = { color: '#0000FF', weight: 4 };
var defaultTrackOpts = { color: '#ff0000', weight: 3 };
var selectedTrackCoords = null;
var trackProgressbar = document.getElementById('track-progressbar');
var trackProgressbarContainer = document.getElementById('track-progressbar-container');
var trackProgressbarFill = document.getElementById('track-progressbar-fill');
var trackProgressbarHoverdot = document.getElementById('track-progressbar-hoverdot');
var movingMarker = null;
function haversine(latlng1, latlng2) {
  var R = 6371; // km
  var dLat = (latlng2[0] - latlng1[0]) * Math.PI / 180;
  var dLon = (latlng2[1] - latlng1[1]) * Math.PI / 180;
  var lat1 = latlng1[0] * Math.PI / 180;
  var lat2 = latlng2[0] * Math.PI / 180;
  var a = Math.sin(dLat/2)*Math.sin(dLat/2) +
          Math.sin(dLon/2)*Math.sin(dLon/2)*Math.cos(lat1)*Math.cos(lat2);
  var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  return R * c;
}
function computeCumulativeDistances(coords) {
  var dists = [0];
  for (var i = 1; i < coords.length; ++i) {
    var d = haversine(coords[i-1], coords[i]);
    dists.push(dists[i-1] + d);
  }
  return dists;
}
var cumulativeDistances = null;
function showProgressbar(coords) {
  selectedTrackCoords = coords;
  cumulativeDistances = computeCumulativeDistances(coords);
  trackProgressbarContainer.style.display = 'block';
  trackProgressbarFill.style.width = '0%';
  trackProgressbarHoverdot.style.display = 'none';
  document.getElementById('track-progressbar-distlabel').style.display = 'none';
  var totalDist = cumulativeDistances.length > 0 ? cumulativeDistances[cumulativeDistances.length-1] : 0;
  document.getElementById('track-progressbar-totaldist').textContent = "File: " + selectedTrackFilename + " | Total distance: " + totalDist.toFixed(2) + " km";
  if (movingMarker) {
    map.removeLayer(movingMarker);
    movingMarker = null;
  }
}
function hideProgressbar() {
  trackProgressbarContainer.style.display = 'none';
  selectedTrackCoords = null;
  if (movingMarker) {
    map.removeLayer(movingMarker);
    movingMarker = null;
  }
}
function handleProgressTouch(e) {
  if (!selectedTrackCoords || !cumulativeDistances) return;
  var rect = trackProgressbar.getBoundingClientRect();
  var touch = e.touches[0];
  var percent = (touch.clientX - rect.left) / rect.width;
  percent = Math.max(0, Math.min(1, percent));
  var idx = Math.round(percent * (selectedTrackCoords.length - 1));
  var latlng = selectedTrackCoords[idx];
  trackProgressbarHoverdot.style.display = 'block';
  trackProgressbarHoverdot.style.left = (percent * 100) + '%';
  var distlabel = document.getElementById('track-progressbar-distlabel');
  distlabel.style.display = 'block';
  distlabel.style.left = (percent * 100) + '%';
  var dist = cumulativeDistances[idx];
  var total = cumulativeDistances[cumulativeDistances.length-1];
  distlabel.textContent = dist.toFixed(2) + ' km of ' + total.toFixed(2) + ' km';
  if (!movingMarker) {
    movingMarker = L.circleMarker(latlng, {radius: 8, color: '#00ff00', fillColor: '#00ff00', fillOpacity: 0.8});
    movingMarker.addTo(map);
  } else {
    movingMarker.setLatLng(latlng);
  }
  e.preventDefault();
}
trackProgressbar.addEventListener('mousemove', function(e) {
  if (!selectedTrackCoords || !cumulativeDistances) return;
  var rect = trackProgressbar.getBoundingClientRect();
  var percent = (e.clientX - rect.left) / rect.width;
  percent = Math.max(0, Math.min(1, percent));
  var idx = Math.round(percent * (selectedTrackCoords.length - 1));
  var latlng = selectedTrackCoords[idx];
  trackProgressbarHoverdot.style.display = 'block';
  trackProgressbarHoverdot.style.left = (percent * 100) + '%';
  var distlabel = document.getElementById('track-progressbar-distlabel');
  distlabel.style.display = 'block';
  distlabel.style.left = (percent * 100) + '%';
  var dist = cumulativeDistances[idx];
  var total = cumulativeDistances[cumulativeDistances.length-1];
  distlabel.textContent = dist.toFixed(2) + ' km of ' + total.toFixed(2) + ' km';
  if (!movingMarker) {
    movingMarker = L.circleMarker(latlng, {radius: 8, color: '#00ff00', fillColor: '#00ff00', fillOpacity: 0.8});
    movingMarker.addTo(map);
  } else {
    movingMarker.setLatLng(latlng);
  }
});
trackProgressbar.addEventListener('mouseleave', function() {
  trackProgressbarHoverdot.style.display = 'none';
  var distlabel = document.getElementById('track-progressbar-distlabel');
  distlabel.style.display = 'none';
  if (movingMarker && selectedTrackCoords) movingMarker.setLatLng(selectedTrackCoords[0]);
});
trackProgressbar.addEventListener('touchstart', handleProgressTouch, {passive: false});
trackProgressbar.addEventListener('touchmove', handleProgressTouch, {passive: false});
trackProgressbar.addEventListener('touchend', function() {});

document.getElementById('loader').style.display = 'flex';
const basePath = new URL('./', window.location.href).href;
const geoDataUrl = basePath + 'geo_data.json.gz?v=""" + str(geo_data_mtime) + """';
const trackPolylinesByFilename = {};
fetch(geoDataUrl)
  .then(response => response.json())
  .then(data => {

    data.tracks.forEach(track => {
      trackPolylinesByFilename[track.filename] = [];
      track.segments.forEach(segment => {
        var polyline = L.polyline(segment, defaultTrackOpts)
          .bindPopup("<small style='font-size:10px'>" + track.filename + "</small>");
        trackPolylinesByFilename[track.filename].push(polyline);
    
        polyline.on('click', function(e) {
          Object.values(trackPolylinesByFilename).forEach(polylines => {
            polylines.forEach(pl => {
              pl.setStyle(defaultTrackOpts);
              pl.bringToBack();
            });
          });
          trackPolylinesByFilename[track.filename].forEach(pl => {
            pl.setStyle(selectedTrackOpts);
            pl.bringToFront();
          });
    
          polyline.openPopup(e.latlng);
    
          selectedTrackFilename = track.filename;
          selectedTrackCoords = track.coords;
          showProgressbar(track.coords);
    
          L.DomEvent.stopPropagation(e);
        });

    tracksLayer.addLayer(polyline);
  });
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
      marker.on('mouseover', function(e) {
        marker.openPopup();
      });
      marker.on('mouseout', function(e) {
        marker.closePopup();
      });
      if (pt.filename.includes("TODO")) {
        marker.addTo(todoMarkersLayer);
      } else {
        marker.addTo(otherMarkersLayer);
      }
    });
  });
fetch(basePath + 'deepstate.geojson?v=""" + str(deepstate_mtime) + """')
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
Object.entries(overlays).forEach(([name, layer]) => {
    if (activeLayers.includes(name)) map.addLayer(layer);
});
L.control.layers(null, overlays, {collapsed: false, position: 'bottomright'}).addTo(map);
L.control.locate({
  position: 'bottomleft',
  flyTo: true,
  strings: { title: "My location" },
  locateOptions: { enableHighAccuracy: true },
  icon: 'fa fa-crosshairs'
}).addTo(map);
function updateUrl() {
    const center = map.getCenter();
    const zoom = map.getZoom();
    const layersOn = [];
    Object.entries(overlays).forEach(([name, l]) => {
        if (map.hasLayer(l)) layersOn.push(name);
    });
    const base = currentBaseLayer === esriLayer ? 'esri' : 'osm';
    setUrlParams({
        lat: center.lat.toFixed(6),
        lng: center.lng.toFixed(6),
        zoom: zoom,
        layers: layersOn.join(","),
        base: base
    });
}
map.on('moveend zoomend', updateUrl);
map.on('overlayadd overlayremove', updateUrl);
map.on('click', function() {
  if (selectedTrackFilename) {
    trackPolylinesByFilename[selectedTrackFilename].forEach(pl => {
      pl.setStyle(defaultTrackOpts);
      pl.bringToBack();
    });
    selectedTrackFilename = null;
    hideProgressbar();
  }
});
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
                    track, points, named_points = parse_gpx_file(file_path)
                    if track:
                        all_tracks.append(track)
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
