from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Location, PathPoint
import json
import os
import struct
from datetime import datetime, timedelta
from io import BytesIO
import threading
import math

SHAPEFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shapefiles')
if not os.path.exists(SHAPEFILE_DIR):
    os.makedirs(SHAPEFILE_DIR)

recording_devices = set()
last_update_times = {}

@csrf_exempt
def update_location(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print(f"Received data: {data}")

            device_id = data.get('device_id')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            battery = data.get('battery')
            model = data.get('model')

            required_fields = {'device_id': device_id, 'latitude': latitude, 'longitude': longitude, 'battery': battery, 'model': model}
            missing_fields = [field for field, value in required_fields.items() if value is None]
            if missing_fields:
                return JsonResponse({'status': 'error', 'message': f'Missing fields: {missing_fields}'}, status=400)

            try:
                latitude = float(latitude) if isinstance(latitude, (str, int, float)) else None
                longitude = float(longitude) if isinstance(longitude, (str, int, float)) else None
                battery = int(float(battery)) if isinstance(battery, (str, int, float)) else None
            except (ValueError, TypeError) as e:
                return JsonResponse({'status': 'error', 'message': f'Invalid data types: {str(e)}'}, status=400)

            if latitude is None or longitude is None or battery is None:
                return JsonResponse({'status': 'error', 'message': 'Failed to convert latitude, longitude, or battery to correct types'}, status=400)

            if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
                return JsonResponse({'status': 'error', 'message': 'Latitude or longitude out of valid range'}, status=400)

            location, created = Location.objects.update_or_create(
                device_id=device_id,
                defaults={'latitude': latitude, 'longitude': longitude, 'battery': battery, 'model': model}
            )

            last_update_times[device_id] = datetime.now()

            if device_id in recording_devices:
                PathPoint.objects.create(device_id=device_id, latitude=latitude, longitude=longitude, timestamp=datetime.now())

            return JsonResponse({'status': 'success'})
        except json.JSONDecodeError as e:
            return JsonResponse({'status': 'error', 'message': f'Invalid JSON: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

def cleanup_stale_data():
    while True:
        current_time = datetime.now()
        inactive_threshold = current_time - timedelta(seconds=30)
        stale_devices = [device_id for device_id, last_time in last_update_times.items() if last_time < inactive_threshold]
        for device_id in stale_devices:
            Location.objects.filter(device_id=device_id).delete()
            PathPoint.objects.filter(device_id=device_id).delete()
            last_update_times.pop(device_id, None)
            print(f"Cleaned up stale data for device: {device_id}")
        threading.Event().wait(5)

threading.Thread(target=cleanup_stale_data, daemon=True).start()

def get_locations(request):
    locations = Location.objects.all().order_by('-last_updated')
    data = [{'device_id': loc.device_id, 'latitude': loc.latitude, 'longitude': loc.longitude, 'battery': loc.battery, 'model': loc.model, 'last_updated': loc.last_updated.isoformat()} for loc in locations]
    print(f"Returning locations: {data}")
    return JsonResponse(data, safe=False)

@csrf_exempt
def toggle_recording(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            device_id = data.get('device_id')
            action = data.get('action')

            if not device_id or action not in ['start', 'stop']:
                return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

            if action == 'start':
                recording_devices.add(device_id)
            else:
                recording_devices.discard(device_id)
                points = list(PathPoint.objects.filter(device_id=device_id).order_by('timestamp').values_list('latitude', 'longitude'))
                if not points or len(points) < 2:
                    return JsonResponse({'status': 'error', 'message': 'Not enough path data to export (need at least 2 points)'}, status=400)

                shp_buffer = BytesIO()
                write_shp_header(shp_buffer, points)
                write_shp_record(shp_buffer, points, 1)
                shp_path = os.path.join(SHAPEFILE_DIR, f'{device_id}_path.shp')
                with open(shp_path, 'wb') as f:
                    f.write(shp_buffer.getvalue())
                shp_buffer.close()

                shx_buffer = BytesIO()
                write_shx_header(shx_buffer, 1, points)
                content_length_bytes = 4 + 4*8 + 4 + 4 + 4 + 16*len(points)
                write_shx_record(shx_buffer, 50, content_length_bytes // 2)
                shx_path = os.path.join(SHAPEFILE_DIR, f'{device_id}_path.shx')
                with open(shx_path, 'wb') as f:
                    f.write(shx_buffer.getvalue())
                shx_buffer.close()

                dbf_buffer = BytesIO()
                write_dbf_header(dbf_buffer, 1)
                write_dbf_record(dbf_buffer, 1, points[0][0], points[0][1])
                dbf_buffer.write(b'\x1A')
                dbf_path = os.path.join(SHAPEFILE_DIR, f'{device_id}_path.dbf')
                with open(dbf_path, 'wb') as f:
                    f.write(dbf_buffer.getvalue())
                dbf_buffer.close()

                prj_content = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433],AUTHORITY["EPSG","4326"]]'
                prj_path = os.path.join(SHAPEFILE_DIR, f'{device_id}_path.prj')
                with open(prj_path, 'w', encoding='utf-8') as f:
                    f.write(prj_content)

                base_url = request.build_absolute_uri('/api')
                return JsonResponse({
                    'status': 'success',
                    'device_id': device_id,
                    'message': 'Recording stopped. Shapefile saved on server.',
                    'download_links': {
                        'shp': f'{base_url}/export_shp/{device_id}/',
                        'shx': f'{base_url}/export_shx/{device_id}/',
                        'dbf': f'{base_url}/export_dbf/{device_id}/',
                        'prj': f'{base_url}/export_prj/{device_id}/'
                    }
                })
            return JsonResponse({'status': 'success', 'recording': device_id in recording_devices})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

def get_path(request, device_id):
    points = PathPoint.objects.filter(device_id=device_id).order_by('timestamp')
    data = [{'latitude': point.latitude, 'longitude': point.longitude, 'timestamp': point.timestamp.isoformat()} for point in points]

    speed_kmh = None
    if len(points) >= 2:
        point1 = points[len(points) - 2]
        point2 = points[len(points) - 1]

        lat1 = float(point1.latitude)
        lon1 = float(point1.longitude)
        lat2 = float(point2.latitude)
        lon2 = float(point2.longitude)

        R = 6371000
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        time1 = point1.timestamp
        time2 = point2.timestamp
        time_diff = (time2 - time1).total_seconds()

        print(f"Speed Calculation for {device_id}:")
        print(f"Point 1: ({lat1}, {lon1}) at {time1}")
        print(f"Point 2: ({lat2}, {lon2}) at {time2}")
        print(f"Distance: {distance} meters, Time Diff: {time_diff} seconds")

        if time_diff > 0:
            speed_ms = distance / time_diff
            speed_kmh = speed_ms * 3.6
            speed_kmh = round(speed_kmh, 2)
            print(f"Calculated Speed: {speed_kmh} km/h")
        else:
            print("Time difference is 0, cannot calculate speed.")
    else:
        print(f"Not enough points to calculate speed for {device_id}. Points: {len(points)}")

    return JsonResponse({'points': data, 'speed_kmh': speed_kmh})

def map_view(request):
    return render(request, 'map.html')

def export_shp(request, device_id):
    shp_path = os.path.join(SHAPEFILE_DIR, f'{device_id}_path.shp')
    if not os.path.exists(shp_path):
        return JsonResponse({'status': 'error', 'message': 'Shapefile not found'}, status=404)
    return FileResponse(open(shp_path, 'rb'), as_attachment=True, filename=f'{device_id}_path.shp')

def export_shx(request, device_id):
    shx_path = os.path.join(SHAPEFILE_DIR, f'{device_id}_path.shx')
    if not os.path.exists(shx_path):
        return JsonResponse({'status': 'error', 'message': 'Shapefile index not found'}, status=404)
    return FileResponse(open(shx_path, 'rb'), as_attachment=True, filename=f'{device_id}_path.shx')

def export_dbf(request, device_id):
    dbf_path = os.path.join(SHAPEFILE_DIR, f'{device_id}_path.dbf')
    if not os.path.exists(dbf_path):
        return JsonResponse({'status': 'error', 'message': 'Shapefile attributes not found'}, status=404)
    return FileResponse(open(dbf_path, 'rb'), as_attachment=True, filename=f'{device_id}_path.dbf')

def export_prj(request, device_id):
    prj_path = os.path.join(SHAPEFILE_DIR, f'{device_id}_path.prj')
    if not os.path.exists(prj_path):
        return JsonResponse({'status': 'error', 'message': 'Shapefile projection not found'}, status=404)
    return FileResponse(open(prj_path, 'rb'), as_attachment=True, filename=f'{device_id}_path.prj')

def write_shp_header(buffer, points):
    file_code = 9994
    unused = 0
    num_points = len(points)
    num_parts = 1
    content_length_bytes = 4 + 4*8 + 4 + 4 + 4*num_parts + 16*num_points
    file_length = 50 + (8 + content_length_bytes) // 2
    version = 1000
    shape_type = 3
    lons = [float(p[1]) for p in points]
    lats = [float(p[0]) for p in points]
    xmin = min(lons) if lons else 0.0
    ymin = min(lats) if lats else 0.0
    xmax = max(lons) if lons else 0.0
    ymax = max(lats) if lats else 0.0
    zmin, zmax, mmin, mmax = 0.0, 0.0, 0.0, 0.0

    print(f"Shapefile Header - File Length: {file_length} 16-bit words")
    buffer.write(struct.pack('>iiiiiii', file_code, unused, unused, unused, unused, unused, file_length))
    buffer.write(struct.pack('<ii', version, shape_type))
    buffer.write(struct.pack('<dddddddd', xmin, ymin, xmax, ymax, zmin, zmax, mmin, mmax))

def write_shp_record(buffer, points, num_parts):
    record_number = 1
    num_points = len(points)
    content_length_bytes = 4 + 4*8 + 4 + 4 + 4*num_parts + 16*num_points
    content_length = content_length_bytes // 2

    print(f"Shapefile Record - Content Length: {content_length} 16-bit words")
    buffer.write(struct.pack('>ii', record_number, content_length))

    shape_type = 3
    lons = [float(p[1]) for p in points]
    lats = [float(p[0]) for p in points]
    xmin = min(lons) if lons else 0.0
    ymin = min(lats) if lats else 0.0
    xmax = max(lons) if lons else 0.0
    ymax = max(lats) if lats else 0.0
    parts = [0]

    buffer.write(struct.pack('<i', shape_type))
    buffer.write(struct.pack('<dddd', xmin, ymin, xmax, ymax))
    buffer.write(struct.pack('<ii', num_parts, num_points))
    for part in parts:
        buffer.write(struct.pack('<i', part))
    for lon, lat in zip(lons, lats):
        buffer.write(struct.pack('<dd', lon, lat))

def write_shx_header(buffer, num_records, points):
    file_code = 9994
    unused = 0
    file_length = 50 + num_records * 4
    version = 1000
    shape_type = 3
    lons = [float(p[1]) for p in points]
    lats = [float(p[0]) for p in points]
    xmin = min(lons) if lons else 0.0
    ymin = min(lats) if lats else 0.0
    xmax = max(lons) if lons else 0.0
    ymax = max(lats) if lats else 0.0
    zmin, zmax, mmin, mmax = 0.0, 0.0, 0.0, 0.0

    print(f"Index File Header - File Length: {file_length} 16-bit words")
    buffer.write(struct.pack('>iiiiiii', file_code, unused, unused, unused, unused, unused, file_length))
    buffer.write(struct.pack('<ii', version, shape_type))
    buffer.write(struct.pack('<dddddddd', xmin, ymin, xmax, ymax, zmin, zmax, mmin, mmax))

def write_shx_record(buffer, offset, content_length):
    print(f"Index Record - Offset: {offset}, Content Length: {content_length} 16-bit words")
    buffer.write(struct.pack('>ii', offset, content_length))

def write_dbf_header(buffer, num_records):
    year, month, day = datetime.now().timetuple()[:3]
    num_fields = 3
    header_length = 32 + (num_fields * 32) + 1
    record_length = 1 + 10 + 20 + 20

    buffer.write(struct.pack('<BBBBLHH20x', 3, year - 1900, month, day,
                             num_records, header_length, record_length))

    buffer.write(struct.pack('<11sc4xBB14x', b'FID', b'C', 10, 0))
    buffer.write(struct.pack('<11sc4xBB14x', b'Latitude', b'C', 20, 0))
    buffer.write(struct.pack('<11sc4xBB14x', b'Longitude', b'C', 20, 0))

    buffer.write(struct.pack('B', 0x0D))

    print(f"DBF Header - Records: {num_records}, Header Length: {header_length}, Record Length: {record_length}")
    buffer.write(struct.pack('<BBBBLHH20x', 3, year - 1900, month, day, num_records, header_length, record_length))
    buffer.write(struct.pack('<11sBBBB14x', b'FID', 78, 10, 0, 0))
    buffer.write(struct.pack('<11sBBBB14x', b'Latitude', 78, 13, 6, 0))
    buffer.write(struct.pack('<11sBBBB14x', b'Longitude', 78, 13, 6, 0))
    buffer.write(struct.pack('<B', 0x0D))

def write_dbf_record(buffer, fid, lat, lon):
    deletion_flag = b' '
    fid_str = str(fid).ljust(10)[:10].encode('ascii')
    lat_str = f"{lat:.6f}".rjust(20)[:20].encode('ascii')
    lon_str = f"{lon:.6f}".rjust(20)[:20].encode('ascii')

    buffer.write(struct.pack('<B', ord(deletion_flag)))
    buffer.write(fid_str)
    buffer.write(lat_str)
    buffer.write(lon_str)