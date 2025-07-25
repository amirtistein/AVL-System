from django.urls import path
from . import views

urlpatterns = [
    path('api/map/', views.map_view, name='map_view'),
    path('api/location/', views.update_location, name='update_location'),
    path('api/locations/', views.get_locations, name='get_locations'),
    path('api/toggle_recording/', views.toggle_recording, name='toggle_recording'),
    path('api/path/<str:device_id>/', views.get_path, name='get_path'),
    path('api/export_shp/<str:device_id>/', views.export_shp, name='export_shp'),
    path('api/export_shx/<str:device_id>/', views.export_shx, name='export_shx'),
    path('api/export_dbf/<str:device_id>/', views.export_dbf, name='export_dbf'),
    path('api/export_prj/<str:device_id>/', views.export_prj, name='export_prj'),
]