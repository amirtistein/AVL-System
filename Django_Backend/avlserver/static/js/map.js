var map = L.map('map').setView([35.7246, 51.3876], 18);

var baseMaps = {
    osm: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }),
    satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: '© Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    })
};

baseMaps.osm.addTo(map);

var markers = {};
var paths = {};
var deviceSelect = document.getElementById('deviceSelect');
var baseMapSelect = document.getElementById('baseMapSelect');
var downloadSection = document.getElementById('downloadSection');
var downloadShp = document.getElementById('downloadShp');
var downloadShx = document.getElementById('downloadShx');
var downloadDbf = document.getElementById('downloadDbf');
var downloadPrj = document.getElementById('downloadPrj');

// Update device dropdown without resetting selection
function updateDeviceDropdown() {
    const currentSelectedId = deviceSelect.value;

    fetch('/api/locations/')
        .then(response => response.json())
        .then(data => {
            // If new devices are added or removed, refresh the dropdown
            const currentDeviceIds = Array.from(deviceSelect.options).slice(1).map(opt => opt.value);
            const serverDeviceIds = data.map(loc => loc.device_id);

            const listsAreSame = currentDeviceIds.length === serverDeviceIds.length &&
                                 currentDeviceIds.every(id => serverDeviceIds.includes(id));

            if (listsAreSame) {
                // Only update battery label for selected
                const selected = data.find(d => d.device_id === currentSelectedId);
                if (selected) {
                    const selectedOption = [...deviceSelect.options].find(opt => opt.value === selected.device_id);
                    if (selectedOption) {
                        selectedOption.text = `${selected.model} (${selected.device_id}) - ${selected.battery}%`;
                    }
                }
                return;
            }

            // Refresh the dropdown if device list has changed
            deviceSelect.innerHTML = '<option value="">-- Select a Device --</option>';
            data.forEach(loc => {
                const option = document.createElement('option');
                option.value = loc.device_id;
                option.text = `${loc.model} (${loc.device_id}) - ${loc.battery}%`;
                deviceSelect.appendChild(option);
            });

            // Restore previous selection
            if (serverDeviceIds.includes(currentSelectedId)) {
                deviceSelect.value = currentSelectedId;
            }
        })
        .catch(error => console.error('Error updating device dropdown:', error));
}


function updateBaseMap() {
    const selectedBaseMap = baseMapSelect.value;
    Object.keys(baseMaps).forEach(key => {
        if (map.hasLayer(baseMaps[key])) {
            map.removeLayer(baseMaps[key]);
        }
    });
    baseMaps[selectedBaseMap].addTo(map);
}

function updateMapForSelectedDevice() {
    const selectedDeviceId = deviceSelect.value;

    // Remove all previous markers and paths
    for (let id in markers) {
        map.removeLayer(markers[id]);
    }
    for (let id in paths) {
        map.removeLayer(paths[id]);
    }
    markers = {};
    paths = {};

    if (!selectedDeviceId) return;

    fetch(`/api/locations/`)
        .then(res => res.json())
        .then(data => {
            // Filter ONLY selected device
            const selectedDevice = data.find(loc => loc.device_id === selectedDeviceId);
            if (!selectedDevice) return;

            const latlng = [selectedDevice.latitude, selectedDevice.longitude];
            const popup = `
                <b>Device:</b> ${selectedDevice.model} (${selectedDevice.device_id})<br>
                <b>Battery:</b> ${selectedDevice.battery}%<br>
                <b>Lat:</b> ${selectedDevice.latitude}<br>
                <b>Lon:</b> ${selectedDevice.longitude}
            `;

            const marker = L.marker(latlng).bindPopup(popup).addTo(map);
            markers[selectedDeviceId] = marker;
            marker.openPopup();
            map.setView(latlng, 18);
        });

    fetch(`/api/path/${selectedDeviceId}/`)
        .then(res => res.json())
        .then(points => {
            if (points.length < 2) return;
            const latlngs = points.map(p => [p.latitude, p.longitude]);
            const polyline = L.polyline(latlngs, { color: 'blue' }).addTo(map);
            paths[selectedDeviceId] = polyline;
            map.fitBounds(L.latLngBounds(latlngs), { padding: [50, 50] });
        });
}


// Periodic update
setInterval(updateDeviceDropdown, 10000);             // Refresh device list
setInterval(updateMapForSelectedDevice, 5000);        // Refresh map for selected device

// Manual select change
deviceSelect.addEventListener('change', updateMapForSelectedDevice);

// Base map change
baseMapSelect.addEventListener('change', updateBaseMap);

// Initial run
updateDeviceDropdown();
