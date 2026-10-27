import math


UNIT_TO_METERS = {"cm": 0.01, "m": 1.0, "km": 1000.0}


def manual_area(side_a: float, side_b: float, side_c: float, side_d: float, unit: str) -> tuple[list[float], float]:
    sides = [value * UNIT_TO_METERS[unit] for value in (side_a, side_b, side_c, side_d)]
    area = ((sides[0] + sides[2]) / 2) * ((sides[1] + sides[3]) / 2)
    return sides, area


def polygon_area_m2(geojson: dict) -> float:
    if geojson.get("type") != "Polygon":
        raise ValueError("Boundary must be a GeoJSON Polygon")
    rings = geojson.get("coordinates") or []
    if not rings or len(rings[0]) < 4:
        raise ValueError("Boundary requires at least three points")
    points = rings[0]
    if points[0] != points[-1]:
        points = [*points, points[0]]
    radius = 6_371_008.8
    total = 0.0
    for index in range(len(points) - 1):
        lon1, lat1 = map(math.radians, points[index])
        lon2, lat2 = map(math.radians, points[index + 1])
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    area = abs(total * radius * radius / 2)
    if area <= 0 or area > 100_000_000:
        raise ValueError("Boundary area is outside the supported 0–10,000 hectare range")
    return area

