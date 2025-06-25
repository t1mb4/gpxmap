# GPXMap

An interactive GPX map viewer for displaying tracks, custom waypoints (POIs), heatmaps and DeepState polygon overlays.  
Supports map layer toggling, heatmap control, basemap switching (OSM / ArcGIS), and geolocation.

---

## Screenshots:

<table>
  <tr>
    <td><img src="docs/img/1.png" alt="screenshot 1" width="300"/></td>
    <td><img src="docs/img/2.png" alt="screenshot 2" width="300"/></td>
    <td><img src="docs/img/3.png" alt="screenshot 3" width="300"/></td>
  </tr>
  <tr>
    <td><img src="docs/img/4.png" alt="screenshot 4" width="300"/></td>
    <td><img src="docs/img/5.png" alt="screenshot 5" width="300"/></td>
    <td><img src="docs/img/6.png" alt="screenshot 6" width="300"/></td>
  </tr>
</table>

---

## Installation

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

---

## Usage

mkdir tracks; cp path/to/tracks/*.gpx tracks
OR
ln -s path/to/tracks/ tracks

./gen.py --html --geodata

Place index.html and geo_data.json.gz in docroot on webserver

Create vhost, add this location in vhost:

location ~ geo_data.json.gz {
    gzip off;
    add_header Content-Encoding gzip;
    add_header Content-Type application/json;
}


???????
PROFIT
