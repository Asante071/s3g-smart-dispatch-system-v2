
"""Road routing service using the OSRM routing API."""

from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import json


class RoutingService:
    """Retrieve road distance and estimated driving duration."""

    def __init__(self, base_url="https://router.project-osrm.org",
                 timeout=5):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_route(self, origin, destination):
        """
        Coordinates must be dictionaries containing latitude and longitude.

        Returns road distance in kilometres and duration in minutes,
        or None when a reliable route cannot be obtained.
        """
        if not self._valid_coordinates(origin):
            return None

        if not self._valid_coordinates(destination):
            return None

        origin_coordinates = (
            f"{origin['longitude']},{origin['latitude']}"
        )
        destination_coordinates = (
            f"{destination['longitude']},{destination['latitude']}"
        )

        coordinates = (
            f"{origin_coordinates};{destination_coordinates}"
        )

        url = (
            f"{self.base_url}/route/v1/driving/"
            f"{quote(coordinates, safe=';,.')}"
            "?overview=false&alternatives=false&steps=false"
        )

        request = Request(
            url,
            headers={"User-Agent": "S3G-Smart-Dispatch-System/1.0"}
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))

            if payload.get("code") != "Ok":
                return None

            routes = payload.get("routes", [])

            if not routes:
                return None

            route = routes[0]
            distance_metres = route.get("distance")
            duration_seconds = route.get("duration")

            if not self._valid_number(distance_metres):
                return None

            if not self._valid_number(duration_seconds):
                return None

            if distance_metres < 0 or duration_seconds < 0:
                return None

            return {
                "distance_km": round(distance_metres / 1000, 3),
                "duration_minutes": round(duration_seconds / 60, 2),
                "provider": "OSRM",
                "status": "success"
            }

        except (HTTPError, URLError, TimeoutError, OSError,
                ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def _valid_coordinates(coordinates):
        if not isinstance(coordinates, dict):
            return False

        latitude = coordinates.get("latitude")
        longitude = coordinates.get("longitude")

        return (
            RoutingService._valid_number(latitude)
            and RoutingService._valid_number(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        )

    @staticmethod
    def _valid_number(value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isfinite(value)
        )
