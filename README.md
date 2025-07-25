
# Real-Time AVL System using Django and Android

This project is a lightweight Automatic Vehicle Location (AVL) system developed using **Django (Python)** for the backend and **Android Studio (Java)** for the mobile client.

## 📱 Mobile App (Android - Java)

The Android application collects and sends real-time data to the Django server, including:
- **Latitude and Longitude**
- **Phone ID and Device Type**
- **Battery Percentage**

This data is transmitted continuously to the server, allowing the system to track multiple devices simultaneously.

## 🌐 Server & Web Interface (Django)

The Django server:
- Displays user locations on an interactive **basemap** (supporting base map switching).
- **Tracks user movement** in real-time.
- **Calculates speed** on the backend.
- **Saves movement paths** as both **GeoJSON** and **Shapefiles**.
- Implements a **boundary (geofence)** system:
  - Triggers an **alert** if a user moves outside the defined boundary.

## 🌍 Features

- 🔴 Real-time multi-user tracking  
- 🌐 Customizable interactive map interface  
- 🧾 Data export in GeoJSON and Shapefile formats  
- 🚨 Geofence boundary alert system  
- 📊 Backend speed calculation  
- 🔋 Battery monitoring  

## 🛠 Technologies

- **Backend**: Django, GeoDjango  
- **Frontend (web)**: Leaflet.js or OpenLayers (if used)  
- **Mobile App**: Android Studio (Java)  
- **GIS Tools**: GDAL, GeoJSON, Shapefile handling  
- **Database**: PostgreSQL + PostGIS (recommended for spatial queries)

## 🚀 How to Run

### Django Backend:
1. Clone the repo and navigate to the Django folder
2. Create virtual environment and install requirements:
   ```bash
   pip install -r requirements.txt
