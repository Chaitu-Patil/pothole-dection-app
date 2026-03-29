import cv2
import numpy as np
import math


LANE_WIDTH_METERS = 3.7  # standard road lane width in meters


def detect_shadow_length(image_bytes: bytes) -> dict:

    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return {"success": False, "error": "Could not decode image"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (11, 11), 0)

    # Threshold to isolate dark regions (shadows/potholes)
    # Pixels darker than 60/255 are candidates
    _, dark_mask = cv2.threshold(blurred, 60, 255, cv2.THRESH_BINARY_INV)

    # Clean up noise
    kernel = np.ones((5, 5), np.uint8)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, kernel)
    dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return {"success": False, "error": "No dark regions detected"}

    # Take the largest dark region as the pothole shadow
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)

    # Ignore tiny regions (noise)
    min_area = img.shape[0] * img.shape[1] * 0.005  # at least 0.5% of image
    if area < min_area:
        return {"success": False, "error": "Dark region too small to be a pothole shadow"}

    x, y, w, h = cv2.boundingRect(largest)
    shadow_length_px = max(w, h)  # use the longer dimension

    return {
        "success": True,
        "shadow_length_px": shadow_length_px,
        "image_width_px": img.shape[1],
        "image_height_px": img.shape[0],
        "contour_area": area,
        "bounding_box": {"x": x, "y": y, "w": w, "h": h},
    }


def calculate_depth(shadow_length_px: int, image_width_px: int, sun_elevation_deg: float) -> dict:
    if sun_elevation_deg <= 0:
        return {"success": False, "error": "Sun is below horizon"}

    px_per_meter = image_width_px / LANE_WIDTH_METERS
    shadow_length_m = shadow_length_px / px_per_meter

    elevation_rad = math.radians(sun_elevation_deg)
    depth_m = shadow_length_m * math.tan(elevation_rad)

    # Sanity check: potholes deeper than 30cm are very severe, over 50cm is suspect
    confidence = "high" if depth_m <= 0.30 else "medium" if depth_m <= 0.50 else "low"

    return {
        "success": True,
        "depth_meters": round(depth_m, 3),
        "shadow_length_meters": round(shadow_length_m, 3),
        "confidence": confidence,
    }
