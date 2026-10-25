// ==========================================
// Chart.js Setup & Configurations
// ==========================================
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

// ==========================================
// Temporal Persistence & Stabilization Engine
// ==========================================
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

// Stabilization state trackers
let smoothedDistance = null;
let stableInRadius = false;
let stableOccupied = false;
let lastInsideTimestamp = 0;
let lastOccupiedTimestamp = 0;
let stableDirection = "STATIONARY";
let lastDirectionTimestamp = 0;

const HOLD_TIME_MS = 1200;       // 2.5s hold time eliminates momentary null flickers
const HYSTERESIS_MARGIN = 0.10;  // 25cm barrier prevents flapping right on the radius line

function updateDashboard(payload) {
    const now = Date.now();
    const rawDist = payload.estimated_distance_m;
    const hasDist = (rawDist !== undefined && rawDist !== null);
    const rawOccupied = payload.state !== "VACANT";

    // 1. Exponential Moving Average for calm, fluid distance readouts
    if (hasDist) {
        if (smoothedDistance === null) {
            smoothedDistance = rawDist;
        } else {
            smoothedDistance = (smoothedDistance * 0.82) + (rawDist * 0.18);
        }
    }

    // 2. Occupancy State Hold Timer
    if (rawOccupied) {
        lastOccupiedTimestamp = now;
        stableOccupied = true;
    } else if (now - lastOccupiedTimestamp > HOLD_TIME_MS) {
        stableOccupied = false;
    }

    // 3. Perimeter Geofence Schmitt Trigger (Hysteresis)
    let instantaneousInside = false;
    if (smoothedDistance !== null && stableOccupied) {
        if (stableInRadius) {
            // Must step past radius + hysteresis to clear
            instantaneousInside = (smoothedDistance <= targetRadius + HYSTERESIS_MARGIN);
        } else {
            // Must step cleanly within radius to trip
            instantaneousInside = (smoothedDistance <= targetRadius);
        }
    }

    // 4. In-Radius Persistence (Debounce)
    if (instantaneousInside) {
        lastInsideTimestamp = now;
        stableInRadius = true;
    } else if (now - lastInsideTimestamp > HOLD_TIME_MS) {
        stableInRadius = false;
    }

    // 5. Directional Motion Smoothing
    const rawDirection = payload.direction || "STATIONARY";
    if (rawDirection !== "STATIONARY") {
        stableDirection = rawDirection;
        lastDirectionTimestamp = now;
    } else if (now - lastDirectionTimestamp > 1200) {
        stableDirection = "STATIONARY";
    }

    // ==========================================
    // Stable DOM Updates
    // ==========================================
    const badge = document.getElementById("state-badge");
    const stateDetail = document.getElementById("state-detail");
    const countVal = document.getElementById("headcount-val");
    const confidenceDetail = document.getElementById("confidence-detail");
    const distEl = document.getElementById("distance-val");
    const motionEl = document.getElementById("motion-val");
    const geofenceBadge = document.getElementById("geofence-badge");
    const geofenceDetail = document.getElementById("geofence-detail");
    const meter = document.getElementById("kinetic-meter-bar");
    const kineticVal = document.getElementById("kinetic-val");

    // Distance & Direction readouts
    if (distEl) {
        distEl.innerText = smoothedDistance !== null ? `${smoothedDistance.toFixed(1)} m` : "-- m";
    }
    if (motionEl) {
        motionEl.innerText = stableDirection;
        motionEl.className = `readout-value motion-${stableDirection.toLowerCase()}`;
    }

    // Perimeter Geofence Card
    if (geofenceBadge && geofenceDetail) {
        if (stableOccupied && smoothedDistance !== null) {
            if (stableInRadius) {
                geofenceBadge.innerText = `TARGET IN RADIUS (${smoothedDistance.toFixed(1)}m)`;
                geofenceBadge.className = "geofence-badge geofence-breach";
                geofenceDetail.innerText = `Confirmed occupant within ${targetRadius.toFixed(1)}m perimeter.`;
            } else {
                geofenceBadge.innerText = "OUTSIDE RADIUS";
                geofenceBadge.className = "geofence-badge geofence-outside";
                geofenceDetail.innerText = `Activity at ${smoothedDistance.toFixed(1)}m (filtered outside ${targetRadius.toFixed(1)}m threshold).`;
            }
        } else {
            geofenceBadge.innerText = "PERIMETER CLEAR";
            geofenceBadge.className = "geofence-badge geofence-clear";
            geofenceDetail.innerText = `Monitoring ${targetRadius.toFixed(1)}m radius around adapter.`;
        }
    }

    // Room Occupancy State Card
    if (badge && stateDetail) {
        if (stableOccupied) {
            if (!stableInRadius && targetRadius <= 2.5) {
                badge.innerText = "OUTSIDE PERIMETER";
                badge.className = "state-badge state-vacant";
                stateDetail.innerText = `Activity detected in adjacent room (~${smoothedDistance ? smoothedDistance.toFixed(1) : '?'}m).`;
            } else {
                badge.innerText = "OCCUPIED";
                badge.className = "state-badge state-occupied";
                stateDetail.innerText = "Sustained human presence active in room.";
            }
        } else {
            badge.innerText = "VACANT";
            badge.className = "state-badge state-vacant";
            stateDetail.innerText = "No significant RF perturbation inside perimeter.";
        }
    }

    // Dual Headcount Engine (In-Radius vs Total Room)
    const radiusCountVal = document.getElementById("radius-count-val");
    const geofenceCountVal = document.getElementById("geofence-count-val");

    let totalHeadcount = 0;
    let inRadiusHeadcount = 0;

    if (stableOccupied) {
        // Total RF perturbations in the environment
        totalHeadcount = Math.max(1, payload.headcount || 1);
        
        // Strict in-perimeter headcount
        if (stableInRadius) {
            inRadiusHeadcount = 1;
        } else {
            inRadiusHeadcount = 0;
        }
    }

    if (countVal) countVal.innerText = totalHeadcount;
    if (radiusCountVal) radiusCountVal.innerText = inRadiusHeadcount;
    if (geofenceCountVal) geofenceCountVal.innerText = inRadiusHeadcount;

    if (confidenceDetail) {
        if (stableOccupied) {
            if (stableInRadius) {
                confidenceDetail.innerText = `Target in perimeter (${targetRadius.toFixed(1)}m) | Total detected: ${totalHeadcount}`;
            } else {
                confidenceDetail.innerText = `Filtered: ${totalHeadcount} in room, but outside ${targetRadius.toFixed(1)}m perimeter (~${smoothedDistance ? smoothedDistance.toFixed(1) : '?'}m)`;
            }
        } else {
            confidenceDetail.innerText = `RF Scatter Entropy: ${payload.entropy ? payload.entropy.toFixed(2) : '0.00'} | Baseline Quiet`;
        }
    }

    // Kinetic Energy Meter
    if (meter && kineticVal) {
        const kinetic = payload.kinetic_energy || 0.0;
        const meterPct = Math.min(Math.max((kinetic / 0.5) * 100, 0), 100);
        meter.style.width = `${meterPct}%`;
        kineticVal.innerText = kinetic.toFixed(3);
    }

    // Real-Time Waveform Charts
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

// ==========================================
// Circular RF Sweep Radar Engine (Calm Glider)
// ==========================================
const radarCanvas = document.getElementById("radarCanvas");
const radarCtx = radarCanvas ? radarCanvas.getContext("2d") : null;
let sweepAngle = 0.0;
let animatedBlipDist = null;

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
    radarCtx.strokeStyle = stableInRadius ? "rgba(239, 68, 68, 0.85)" : "rgba(56, 189, 248, 0.6)";
    radarCtx.lineWidth = 1.5;
    radarCtx.stroke();
    radarCtx.restore();

    // 3. Sweeping Beam
    sweepAngle += 0.035;
    if (sweepAngle >= Math.PI * 2) sweepAngle = 0;

    radarCtx.save();
    radarCtx.translate(cx, cy);
    radarCtx.rotate(sweepAngle);
    const grad = radarCtx.createLinearGradient(0, 0, maxRadius, 0);
    grad.addColorStop(0, "rgba(56, 189, 248, 0)");
    grad.addColorStop(1, "rgba(56, 189, 248, 0.3)");
    radarCtx.fillStyle = grad;
    radarCtx.beginPath();
    radarCtx.moveTo(0, 0);
    radarCtx.arc(0, 0, maxRadius, -0.32, 0);
    radarCtx.lineTo(0, 0);
    radarCtx.fill();
    radarCtx.restore();

    // 4. Center Adapter Marker
    radarCtx.beginPath();
    radarCtx.arc(cx, cy, 4, 0, Math.PI * 2);
    radarCtx.fillStyle = "#38bdf8";
    radarCtx.shadowColor = "#38bdf8";
    radarCtx.shadowBlur = 8;
    radarCtx.fill();
    radarCtx.shadowBlur = 0;

    // 5. Smoothly Gliding Target Blip
    if (stableOccupied && smoothedDistance !== null) {
        if (animatedBlipDist === null) {
            animatedBlipDist = smoothedDistance;
        } else {
            // Calm interpolation prevents teleporting
            animatedBlipDist += (smoothedDistance - animatedBlipDist) * 0.08;
        }

        const clampedDist = Math.max(0.3, Math.min(animatedBlipDist, maxMeters));
        const blipR = (clampedDist / maxMeters) * maxRadius;
        const blipX = cx;
        const blipY = cy - blipR;

        // Target Core
        radarCtx.beginPath();
        radarCtx.arc(blipX, blipY, 7, 0, Math.PI * 2);
        radarCtx.fillStyle = stableInRadius ? "#ef4444" : "#3b82f6";
        radarCtx.shadowColor = stableInRadius ? "#ef4444" : "#3b82f6";
        radarCtx.shadowBlur = 12;
        radarCtx.fill();
        radarCtx.shadowBlur = 0;

        // Target Ambient Halo
        radarCtx.beginPath();
        radarCtx.arc(blipX, blipY, 11, 0, Math.PI * 2);
        radarCtx.strokeStyle = stableInRadius ? "rgba(239, 68, 68, 0.45)" : "rgba(59, 130, 246, 0.45)";
        radarCtx.lineWidth = 1.5;
        radarCtx.stroke();
    } else {
        animatedBlipDist = null;
    }

    requestAnimationFrame(renderRadarFrame);
}
requestAnimationFrame(renderRadarFrame);

// ==========================================
// WebSocket Connection Management
// ==========================================
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

    socket.onerror = () => {
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
    .catch(e => console.warn("Status offline:", e));

connectWebSocket();
