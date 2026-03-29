from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timezone
import math

from backend.sun_angle import get_sun_elevation, is_lighting_adequate
from backend.shadow import detect_shadow_length, calculate_depth
from road_data import get_road_data

app = FastAPI(title="Pothole Priority API")

# Allow the frontend to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend files at /
app.mount("/app", StaticFiles(directory="../frontend", html=True), name="frontend")


def compute_damage_score(depth_m: float, speed_mph: int, daily_traffic: int) -> dict:
    depth_cm = depth_m * 100
    depth_score = min(depth_cm, 40)

    speed_score = min((speed_mph / 65) ** 2 * 40, 40)

    traffic_score = min(math.log10(max(daily_traffic, 1)) / math.log10(50000) * 20, 20)

    total = depth_score + speed_score + traffic_score

    if total >= 70:
        priority = "Critical"
    elif total >= 45:
        priority = "High"
    elif total >= 25:
        priority = "Medium"
    else:
        priority = "Low"

    return {
        "total": round(total, 1),
        "priority": priority,
        "breakdown": {
            "depth_score": round(depth_score, 1),
            "speed_score": round(speed_score, 1),
            "traffic_score": round(traffic_score, 1),
        },
    }


@app.post("/api/report")
async def submit_report(
    photo: UploadFile = File(...),
    lat: float = Form(...),
    lon: float = Form(...),
    timestamp: str = Form(...),  # ISO 8601 string e.g. "2025-03-28T14:30:00Z"
):
    # --- Parse timestamp ---
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO 8601.")

    # --- Validate coordinates ---
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Invalid GPS coordinates.")

    # --- Read image ---
    image_bytes = await photo.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty image file.")

    # --- Sun angle ---
    sun_elevation = get_sun_elevation(lat, lon, dt)
    lighting_ok = is_lighting_adequate(sun_elevation)

    if not lighting_ok:
        return {
            "success": False,
            "error": f"Sun angle ({sun_elevation:.1f}°) is outside the reliable range (20-70°). "
                     "Try again when the sun is higher in the sky.",
            "sun_elevation_deg": sun_elevation,
        }

    # --- Shadow detection ---
    shadow_result = detect_shadow_length(image_bytes)
    if not shadow_result["success"]:
        return {
            "success": False,
            "error": shadow_result.get("error", "Shadow detection failed."),
            "sun_elevation_deg": sun_elevation,
        }

    # --- Depth calculation ---
    depth_result = calculate_depth(
        shadow_result["shadow_length_px"],
        shadow_result["image_width_px"],
        sun_elevation,
    )
    if not depth_result["success"]:
        return {"success": False, "error": depth_result.get("error")}

    # --- Road data ---
    road = get_road_data(lat, lon)

    # --- Damage score ---
    score = compute_damage_score(
        depth_result["depth_meters"],
        road["speed_limit_mph"],
        road["daily_traffic"],
    )

    return {
        "success": True,
        "score": score,
        "depth": {
            "meters": depth_result["depth_meters"],
            "cm": round(depth_result["depth_meters"] * 100, 1),
            "confidence": depth_result["confidence"],
        },
        "road": {
            "name": road.get("road_name", "Unknown road"),
            "type": road["road_type"],
            "speed_limit_mph": road["speed_limit_mph"],
            "daily_traffic": road["daily_traffic"],
        },
        "sun_elevation_deg": round(sun_elevation, 1),
        "coordinates": {"lat": lat, "lon": lon},
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
