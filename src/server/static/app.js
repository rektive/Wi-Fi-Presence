const maxDataPoints = 80;
const labels = Array(maxDataPoints).fill("");
const signalData = Array(maxDataPoints).fill(0);
const filteredData = Array(maxDataPoints).fill(0);

const signalCanvas = document.getElementById("signalChart");
const signalCtx = signalCanvas ? signalCanvas.getContext("2d") : null;
const signalChart = signalCtx ? new Chart(signalCtx, {
    type: "line",
    data: {
        labels: labels,
        datasets: [
            {
                label: "Raw Signal (dBm/Latency)",
                data: signalData,
                borderColor: "#0088ff",
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.2
            },
            {
                label: "Hampel Filtered",
                data: filteredData,
                borderColor: "#00e676",
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.2
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
            x: { display: false },
            y: {
                grid: { color: "#233042" },
                ticks: { color: "#94a3b8" }
            }
        },
        plugins: {
            legend: { labels: { color: "#f0f4f8" } }
        }
    }
}) : null;

const dopplerData = Array(maxDataPoints).fill(0);
const dopplerCanvas = document.getElementById("dopplerChart");
const dopplerCtx = dopplerCanvas ? dopplerCanvas.getContext("2d") : null;
const dopplerChart = dopplerCtx ? new Chart(dopplerCtx, {
    type: "line",
    data: {
        labels: labels,
        datasets: [
            {
                label: "Kinetic Motion (0.3 - 5.0 Hz)",
                data: dopplerData,
                borderColor: "#ffd600",
                backgroundColor: "rgba(255, 214, 0, 0.1)",
                fill: true,
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.3
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
            x: { display: false },
            y: {
                grid: { color: "#233042" },
                ticks: { color: "#94a3b8" }
            }
        },
        plugins: {
            legend: { labels: { color: "#f0f4f8" } }
        }
    }
}) : null;

// Radius state management
let targetRadius = parseFloat(localStorage.getItem("geofence_radius") || "2.0");
const radiusInput = document.getElementById("geofence-radius");
if (radiusInput) {
    radiusInput.value = targetRadius;
    radiusInput.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        if (!isNaN(val) && val > 0) {
            targetRadius = val;
            localStorage.setItem("geofence_radius", targetRadius);
        }
    });
}

function updateDashboard(payload) {
    const badge = document.getElementById("state-badge");
    const stateDetail = document.getElementById("state-detail");
    const countVal = document.getElementById("headcount-val");
    const confidenceDetail = document.getElementById("confidence-detail");
    const meter = document.getElementById("kinetic-meter-bar");
    const kineticVal = document.getElementById("kinetic-val");

    const distEl = document.getElementById("distance-val");
    const motionEl = document.getElementById("motion-val");
    const geofenceBadge = document.getElementById("geofence-badge");
    const geofenceDetail = document.getElementById("geofence-detail");

    const dist = payload.estimated_distance_m;
    const direction = payload.direction || "STATIONARY";
    const zone = payload.zone || "";
    const isOccupied = payload.state !== "VACANT";
    const hasDist = (dist !== undefined && dist !== null);
    const isInsideRadius = isOccupied && hasDist && (dist <= targetRadius);
    currentRadarDistance = dist;
    currentRadarOccupied = isOccupied;
    currentRadarBreach = isInsideRadius;

    // 1. Proximity readouts
    if (distEl) {
        distEl.innerText = hasDist ? `${dist.toFixed(1)} m` : "-- m";
    }
    if (motionEl) {
        motionEl.innerText = direction;
        motionEl.className = `readout-value motion-${direction.toLowerCase()}`;
    }

    // 2. Geofence Card Badge
    if (geofenceBadge && geofenceDetail) {
        if (isOccupied && hasDist) {
            if (isInsideRadius) {
                geofenceBadge.innerText = `TARGET IN RADIUS (${dist.toFixed(1)}m)`;
                geofenceBadge.className = "geofence-badge geofence-breach";
                geofenceDetail.innerText = `Breach within ${targetRadius.toFixed(1)}m perimeter! Zone: ${zone}`;
            } else {
                geofenceBadge.innerText = "OUTSIDE RADIUS";
                geofenceBadge.className = "geofence-badge geofence-outside";
                geofenceDetail.innerText = `Activity at ${dist.toFixed(1)}m (outside ${targetRadius.toFixed(1)}m threshold).`;
            }
        } else {
            geofenceBadge.innerText = "PERIMETER CLEAR";
            geofenceBadge.className = "geofence-badge geofence-clear";
            geofenceDetail.innerText = `Monitoring ${targetRadius.toFixed(1)}m radius around adapter.`;
        }
    }

    // 3. Room Occupancy State Card
    if (badge && stateDetail) {
        if (isOccupied) {
            if (!isInsideRadius && hasDist) {
                badge.innerText = "OUTSIDE PERIMETER";
                badge.className = "state-badge state-vacant";
                stateDetail.innerText = `Activity detected in adjacent room (~${dist.toFixed(1)}m), outside ${targetRadius.toFixed(1)}m radius.`;
            } else {
                badge.innerText = payload.state;
                badge.className = `state-badge state-${payload.state.toLowerCase()}`;
                if (payload.state === "ENTERING") {
                    stateDetail.innerText = "Active corridor/doorway entry in progress!";
                } else if (payload.state === "OCCUPIED") {
                    stateDetail.innerText = "Sustained human presence active in room.";
                } else if (payload.state === "EXITING") {
                    stateDetail.innerText = "Motion decreasing; target exiting perimeter.";
                }
            }
        } else {
            badge.innerText = "VACANT";
            badge.className = "state-badge state-vacant";
            stateDetail.innerText = "No significant RF perturbation inside perimeter.";
        }
    }

    // 4. Headcount Card (Gated strictly by user radius)
    if (countVal && confidenceDetail) {
        let inRadiusHeadcount = 0;
        if (isOccupied) {
            if (isInsideRadius) {
                inRadiusHeadcount = Math.max(1, Math.min(payload.headcount, 1));
                confidenceDetail.innerText = `Inside ${targetRadius.toFixed(1)}m | Total RF Scatter: ${payload.headcount}`;
            } else {
                inRadiusHeadcount = 0;
                confidenceDetail.innerText = `Filtered: ${payload.headcount} outside perimeter (~${hasDist ? dist.toFixed(1) : '?'}m)`;
            }
        } else {
            confidenceDetail.innerText = `Entropy: ${payload.entropy ? payload.entropy.toFixed(2) : '0.00'} | Var: ${payload.variance ? payload.variance.toFixed(4) : '0.0000'}`;
        }
        countVal.innerText = inRadiusHeadcount;
    }

    // 5. Kinetic Energy Meter
    if (meter && kineticVal) {
        const kinetic = payload.kinetic_energy || 0.0;
        const meterPct = Math.min(Math.max((kinetic / 0.5) * 100, 0), 100);
        meter.style.width = `${meterPct}%`;
        kineticVal.innerText = kinetic.toFixed(3);
    }

    // 6. Real-time Charts
    if (signalChart && payload.raw_signal !== undefined) {
        signalData.push(payload.raw_signal);
        signalData.shift();
        filteredData.push(payload.filtered_signal);
        filteredData.shift();
        signalChart.update();
    }

    if (dopplerChart && payload.kinetic_energy !== undefined) {
        dopplerData.push(payload.kinetic_energy);
        dopplerData.shift();
        dopplerChart.update();
    }
}

// WebSocket client with automatic reconnect
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;
    const socket = new WebSocket(wsUrl);
    const pill = document.getElementById("connection-pill");

    socket.onopen = () => {
        if (pill) {
            pill.innerText = "Live Connected";
            pill.className = "pill connected";
        }
        setInterval(() => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.send("ping");
            }
        }, 3000);
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        } catch (e) {
            console.error("Telemetry parse error:", e);
        }
    };

    socket.onclose = () => {
        if (pill) {
            pill.innerText = "Disconnected";
            pill.className = "pill disconnected";
        }
        setTimeout(connectWebSocket, 2000);
    };

    socket.onerror = (err) => {
        if (pill) {
            pill.innerText = "Disconnected";
            pill.className = "pill disconnected";
        }
    };
}

fetch("/api/status")
    .then(r => r.json())
    .then(data => {
        const netInfo = document.getElementById("net-info");
        if (netInfo) {
            netInfo.innerText = 
                `Interface: ${data.interface} | Mode: ${data.capture_mode.toUpperCase()} | Rate: ${data.sampling_rate_hz}Hz`;
        }
    })
    .catch(e => console.warn("Status endpoint offline:", e));

connectWebSocket();

// ==========================================
// Circular RF Sweep Radar Engine
// ==========================================
const radarCanvas = document.getElementById("radarCanvas");
const radarCtx = radarCanvas ? radarCanvas.getContext("2d") : null;
let sweepAngle = 0.0;
let currentRadarDistance = null;
let currentRadarOccupied = false;
let currentRadarBreach = false;

function renderRadarFrame() {
    if (!radarCtx || !radarCanvas) return;
    const w = radarCanvas.width;
    const h = radarCanvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const maxMeters = 4.0;
    const maxRadius = cx - 12;

    radarCtx.clearRect(0, 0, w, h);

    // 1. Concentric Range Rings (1m, 2m, 3m, 4m)
    for (let m = 1; m <= 4; m++) {
        const r = (m / maxMeters) * maxRadius;
        radarCtx.beginPath();
        radarCtx.arc(cx, cy, r, 0, Math.PI * 2);
        radarCtx.strokeStyle = "rgba(51, 65, 85, 0.4)";
        radarCtx.lineWidth = 1;
        radarCtx.stroke();

        // Distance text marker
        radarCtx.fillStyle = "rgba(100, 116, 139, 0.7)";
        radarCtx.font = "9px sans-serif";
        radarCtx.fillText(`${m}m`, cx + 3, cy - r + 10);
    }

    // Crosshairs
    radarCtx.beginPath();
    radarCtx.moveTo(cx, 12);
    radarCtx.lineTo(cx, h - 12);
    radarCtx.moveTo(12, cy);
    radarCtx.lineTo(w - 12, cy);
    radarCtx.strokeStyle = "rgba(30, 41, 59, 0.6)";
    radarCtx.stroke();

    // 2. User Perimeter Radius Circle
    const perimeterPx = Math.min((targetRadius / maxMeters) * maxRadius, maxRadius);
    radarCtx.save();
    radarCtx.beginPath();
    radarCtx.arc(cx, cy, perimeterPx, 0, Math.PI * 2);
    radarCtx.setLineDash([4, 4]);
    radarCtx.strokeStyle = currentRadarBreach ? "rgba(239, 68, 68, 0.85)" : "rgba(56, 189, 248, 0.6)";
    radarCtx.lineWidth = 1.5;
    radarCtx.stroke();
    radarCtx.restore();

    // 3. Sweeping Beam
    sweepAngle += 0.04;
    if (sweepAngle >= Math.PI * 2) sweepAngle = 0;

    radarCtx.save();
    radarCtx.translate(cx, cy);
    radarCtx.rotate(sweepAngle);
    const grad = radarCtx.createLinearGradient(0, 0, maxRadius, 0);
    grad.addColorStop(0, "rgba(56, 189, 248, 0)");
    grad.addColorStop(1, "rgba(56, 189, 248, 0.35)");
    radarCtx.fillStyle = grad;
    radarCtx.beginPath();
    radarCtx.moveTo(0, 0);
    radarCtx.arc(0, 0, maxRadius, -0.35, 0);
    radarCtx.lineTo(0, 0);
    radarCtx.fill();
    radarCtx.restore();

    // 4. Center Adapter Marker (PC location)
    radarCtx.beginPath();
    radarCtx.arc(cx, cy, 4, 0, Math.PI * 2);
    radarCtx.fillStyle = "#38bdf8";
    radarCtx.shadowColor = "#38bdf8";
    radarCtx.shadowBlur = 8;
    radarCtx.fill();
    radarCtx.shadowBlur = 0;

    // 5. Target Blip (if person detected)
    if (currentRadarOccupied && currentRadarDistance !== null) {
        const clampedDist = Math.max(0.3, Math.min(currentRadarDistance, maxMeters));
        const blipR = (clampedDist / maxMeters) * maxRadius;
        
        // Fixed upward angle for direct display
        const blipX = cx;
        const blipY = cy - blipR;

        radarCtx.beginPath();
        radarCtx.arc(blipX, blipY, 7, 0, Math.PI * 2);
        radarCtx.fillStyle = currentRadarBreach ? "#ef4444" : "#3b82f6";
        radarCtx.shadowColor = currentRadarBreach ? "#ef4444" : "#3b82f6";
        radarCtx.shadowBlur = 12;
        radarCtx.fill();
        radarCtx.shadowBlur = 0;

        // Ripple ring around blip
        radarCtx.beginPath();
        radarCtx.arc(blipX, blipY, 11, 0, Math.PI * 2);
        radarCtx.strokeStyle = currentRadarBreach ? "rgba(239, 68, 68, 0.5)" : "rgba(59, 130, 246, 0.5)";
        radarCtx.lineWidth = 1.5;
        radarCtx.stroke();
    }

    requestAnimationFrame(renderRadarFrame);
}
requestAnimationFrame(renderRadarFrame);
