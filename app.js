const API_BASE = "http://localhost:8000";

// --- State ---
let gpsCoords = null;
let photoFile = null;

// --- DOM refs ---
const photoInput = document.getElementById("photo-input");
const preview = document.getElementById("preview");
const cameraZone = document.getElementById("camera-zone");
const submitBtn = document.getElementById("submit-btn");
const gpsStatus = document.getElementById("gps-status");
const gpsLabel = document.getElementById("gps-label");

// --- GPS ---
function startGPS() {
  if (!navigator.geolocation) {
    setGPSStatus("error", "Geolocation not supported on this device");
    return;
  }

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      gpsCoords = {
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
        accuracy: pos.coords.accuracy,
      };
      const accText = pos.coords.accuracy < 10
        ? "high accuracy"
        : pos.coords.accuracy < 30
          ? `±${Math.round(pos.coords.accuracy)}m`
          : `low accuracy (±${Math.round(pos.coords.accuracy)}m)`;
      setGPSStatus("ok", `Location locked — ${accText}`);
      checkReadyToSubmit();
    },
    (err) => {
      const msg = err.code === 1
        ? "Location permission denied"
        : err.code === 2
          ? "Location unavailable"
          : "Location request timed out";
      setGPSStatus("error", msg);
    },
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
  );
}

function setGPSStatus(state, message) {
  gpsStatus.className = `gps-status ${state}`;
  gpsLabel.textContent = message;
}

// --- Photo ---
photoInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;

  photoFile = file;
  const url = URL.createObjectURL(file);
  preview.src = url;
  preview.hidden = false;
  cameraZone.classList.add("has-photo");
  checkReadyToSubmit();
});

function checkReadyToSubmit() {
  submitBtn.disabled = !(gpsCoords && photoFile);
}

// --- Submit ---
submitBtn.addEventListener("click", async () => {
  if (!gpsCoords || !photoFile) return;

  showScreen("screen-loading");

  const formData = new FormData();
  formData.append("photo", photoFile);
  formData.append("lat", gpsCoords.lat);
  formData.append("lon", gpsCoords.lon);
  formData.append("timestamp", new Date().toISOString());

  try {
    const res = await fetch(`${API_BASE}/api/report`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showError(err.detail || `Server error (${res.status})`);
      return;
    }

    const data = await res.json();
    displayResults(data);

  } catch (err) {
    showError("Could not reach the server. Make sure the backend is running.");
  }
});

// --- Results ---
function displayResults(data) {
  showScreen("screen-results");

  const errorBox = document.getElementById("error-box");
  const errorMsg = document.getElementById("error-message");

  if (!data.success) {
    errorBox.hidden = false;
    errorMsg.textContent = data.error || "Analysis failed.";

    // Still show sun angle if available
    if (data.sun_elevation_deg !== undefined) {
      document.getElementById("res-sun").textContent =
        `${data.sun_elevation_deg.toFixed(1)}°`;
    }
    return;
  }

  errorBox.hidden = true;

  // Score ring animation
  const score = data.score.total;
  const circumference = 314; // 2 * pi * r (r=50)
  const offset = circumference - (score / 100) * circumference;
  const ring = document.getElementById("ring-fill");

  setTimeout(() => {
    ring.style.strokeDashoffset = offset;
    // Color the ring by priority
    const colors = {
      Critical: "#e8453c",
      High: "#f07030",
      Medium: "#f5c842",
      Low: "#3cb878",
    };
    ring.style.stroke = colors[data.score.priority] || "#f5c842";
  }, 100);

  document.getElementById("score-number").textContent = Math.round(score);

  const badge = document.getElementById("priority-badge");
  badge.textContent = data.score.priority;
  badge.className = `priority-badge ${data.score.priority}`;

  // Detail cards
  document.getElementById("res-depth").textContent =
    `${data.depth.cm} cm`;
  document.getElementById("res-road").textContent =
    data.road.name;
  document.getElementById("res-speed").textContent =
    `${data.road.speed_limit_mph} mph`;
  document.getElementById("res-traffic").textContent =
    data.road.daily_traffic.toLocaleString() + "/day";
  document.getElementById("res-sun").textContent =
    `${data.sun_elevation_deg}°`;
  document.getElementById("res-confidence").textContent =
    capitalise(data.depth.confidence);

  // Score breakdown bars (max possible: depth=40, speed=40, traffic=20)
  const b = data.score.breakdown;
  setTimeout(() => {
    setBar("bar-depth", b.depth_score, 40);
    setBar("bar-speed", b.speed_score, 40);
    setBar("bar-traffic", b.traffic_score, 20);
  }, 200);
}

function setBar(id, value, max) {
  document.getElementById(id).style.width = `${(value / max) * 100}%`;
  document.getElementById(`${id}-label`).textContent =
    value.toFixed(1);
}

function showError(message) {
  showScreen("screen-results");
  document.getElementById("error-box").hidden = false;
  document.getElementById("error-message").textContent = message;
}

// --- Navigation ---
function showScreen(id) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

function resetApp() {
  photoFile = null;
  preview.hidden = true;
  preview.src = "";
  cameraZone.classList.remove("has-photo");
  photoInput.value = "";
  checkReadyToSubmit();
  showScreen("screen-capture");
}

// --- Init ---
startGPS();
