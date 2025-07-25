from django.db import models

class Location(models.Model):
    device_id = models.CharField(max_length=255, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    battery = models.IntegerField()
    model = models.CharField(max_length=255)
    last_updated = models.DateTimeField(auto_now=True)  # Tracks last update time

    def __str__(self):
        return f"{self.device_id} at ({self.latitude}, {self.longitude})"

class PathPoint(models.Model):
    device_id = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Point for {self.device_id} at ({self.latitude}, {self.longitude})"