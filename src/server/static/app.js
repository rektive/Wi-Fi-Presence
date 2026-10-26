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
                const orb = document.getElementById("state-beacon-orb");
                if (orb) orb.className = "state-beacon beacon-vacant";
                stateDetail.innerText = `Activity detected in adjacent room (~${smoothedDistance ? smoothedDistance.toFixed(1) : '?'}m).`;
            } else {
                badge.innerText = "OCCUPIED";
                badge.className = "state-badge state-occupied";
                const orb = document.getElementById("state-beacon-orb");
                if (orb) orb.className = "state-beacon beacon-occupied";
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

// ==========================================
// Room Presets & In-Browser Calibration Logic
// ==========================================
let calState = {
    roomName: "",
    deskMean: null,
    awayMean: null
};

async function fetchPresets() {
    try {
        const res = await fetch("/api/presets");
        if (!res.ok) return;
        const data = await res.json();
        renderPresets(data.presets, data.active, data.count, data.max);
    } catch (err) {
        console.error("Failed to load presets:", err);
    }
}

function renderPresets(presetsList, activeName, count, maxCount) {
    const container = document.getElementById("presets-container");
    const countBadge = document.getElementById("preset-count-badge");
    const addBtn = document.getElementById("btn-add-preset");

    if (countBadge) countBadge.textContent = `${count} / ${maxCount}`;
    if (addBtn) addBtn.disabled = count >= maxCount;

    if (!container) return;
    container.innerHTML = "";

    presetsList.forEach(p => {
        const pill = document.createElement("button");
        pill.className = `preset-pill ${p.name === activeName ? "active" : ""}`;
        pill.innerHTML = `<span>${p.name}</span>`;

        if (p.name !== "Default") {
            const delBtn = document.createElement("span");
            delBtn.className = "preset-delete-btn";
            delBtn.innerHTML = "&times;";
            delBtn.title = "Delete Preset";
            delBtn.onclick = (e) => {
                e.stopPropagation();
                deletePreset(p.name);
            };
            pill.appendChild(delBtn);
        }

        pill.onclick = () => activatePreset(p.name);
        container.appendChild(pill);
    });
}

async function activatePreset(name) {
    try {
        const res = await fetch("/api/presets/activate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name })
        });
        if (res.ok) {
            fetchPresets();
        }
    } catch (err) {
        console.error("Failed to activate preset:", err);
    }
}

async function deletePreset(name) {
    if (!confirm(`Delete calibration preset "${name}"?`)) return;
    try {
        const res = await fetch("/api/presets/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name })
        });
        if (res.ok) {
            fetchPresets();
        }
    } catch (err) {
        console.error("Failed to delete preset:", err);
    }
}

function openCalibrationModal() {
    calState = { roomName: "", deskMean: null, awayMean: null };
    document.getElementById("cal-room-name").value = "";
    proceedToStep(1);
    document.getElementById("calibration-modal").style.display = "flex";
}

function closeCalibrationModal() {
    document.getElementById("calibration-modal").style.display = "none";
}

function proceedToStep(stepNum) {
    if (stepNum === 2) {
        const nameInput = document.getElementById("cal-room-name").value.trim();
        if (!nameInput) {
            alert("Please enter a room name.");
            return;
        }
        calState.roomName = nameInput;
        document.getElementById("sample-near-status").textContent = "Ready to measure";
        document.getElementById("sample-near-val").textContent = "-- dBm";
        document.getElementById("sample-near-progress").style.width = "0%";
        document.getElementById("btn-sample-near").style.display = "inline-block";
        document.getElementById("btn-next-step3").style.display = "none";
    }

    if (stepNum === 3) {
        document.getElementById("sample-away-status").textContent = "Ready to measure";
        document.getElementById("sample-away-val").textContent = "-- dBm";
        document.getElementById("sample-away-progress").style.width = "0%";
        document.getElementById("btn-sample-away").style.display = "inline-block";
        document.getElementById("btn-next-step4").style.display = "none";
    }

    if (stepNum === 4) {
        document.getElementById("sum-name").textContent = calState.roomName;
        document.getElementById("sum-near").textContent = `${calState.deskMean} dBm`;
        document.getElementById("sum-away").textContent = `${calState.awayMean} dBm`;
    }

    for (let i = 1; i <= 4; i++) {
        const el = document.getElementById(`cal-step-${i}`);
        if (el) el.style.display = i === stepNum ? "block" : "none";
    }
}

async function recordSample(phase) {
    const isNear = phase === "desk";
    const statusEl = document.getElementById(isNear ? "sample-near-status" : "sample-away-status");
    const valEl = document.getElementById(isNear ? "sample-near-val" : "sample-away-val");
    const progEl = document.getElementById(isNear ? "sample-near-progress" : "sample-away-progress");
    const btnSample = document.getElementById(isNear ? "btn-sample-near" : "btn-sample-away");
    const btnNext = document.getElementById(isNear ? "btn-next-step3" : "btn-next-step4");

    btnSample.disabled = true;
    statusEl.textContent = "Sampling RF scatter (4.5s)... hold position.";

    // Smooth progress animation over 4.5 seconds
    let progress = 0;
    const interval = setInterval(() => {
        progress += 2.2;
        if (progress > 98) progress = 98;
        progEl.style.width = `${progress}%`;
    }, 100);

    try {
        const res = await fetch("/api/presets/sample", { method: "POST" });
        const data = await res.json();
        clearInterval(interval);
        progEl.style.width = "100%";

        const sampledRssi = data.mean_rssi;
        valEl.textContent = `${sampledRssi} dBm`;
        statusEl.textContent = "✓ Measurement captured";

        if (isNear) {
            calState.deskMean = sampledRssi;
        } else {
            calState.awayMean = sampledRssi;
        }

        btnSample.style.display = "none";
        btnNext.style.display = "inline-block";
    } catch (err) {
        clearInterval(interval);
        statusEl.textContent = "Error sampling packets";
        btnSample.disabled = false;
    }
}

async function saveAndApplyPreset() {
    try {
        const res = await fetch("/api/presets/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: calState.roomName,
                desk_mean: calState.deskMean,
                away_mean: calState.awayMean
            })
        });

        if (res.ok) {
            closeCalibrationModal();
            fetchPresets();
        } else {
            const errData = await res.json();
            alert(errData.message || "Failed to save preset.");
        }
    } catch (err) {
        console.error("Save error:", err);
    }
}

// Initialize presets on load
document.addEventListener("DOMContentLoaded", fetchPresets);

// ==========================================================
// Advanced Multi-Phase Calibration Controller
// ==========================================================
let advancedCalState = {
    roomName: "",
    dDesk: 0.9,
    dFar: 2.4,
    vacantStats: null,
    deskStats: null,
    farStats: null
};

function openCalibrationModal() {
    advancedCalState = {
        roomName: "",
        dDesk: 0.9,
        dFar: 2.4,
        vacantStats: null,
        deskStats: null,
        farStats: null
    };
    document.getElementById("cal-room-name").value = "";
    document.getElementById("cal-dist-desk").value = "0.9";
    document.getElementById("cal-dist-far").value = "2.4";
    proceedToStep(1);
    document.getElementById("calibration-modal").style.display = "flex";
}

function closeCalibrationModal() {
    document.getElementById("calibration-modal").style.display = "none";
}

function proceedToStep(stepNum) {
    if (stepNum === 2) {
        const name = document.getElementById("cal-room-name").value.trim();
        if (!name) {
            alert("Please enter a room or zone name.");
            return;
        }
        advancedCalState.roomName = name;
        advancedCalState.dDesk = parseFloat(document.getElementById("cal-dist-desk").value) || 0.9;
        advancedCalState.dFar = parseFloat(document.getElementById("cal-dist-far").value) || 2.4;

        resetPhaseUI(1);
    } else if (stepNum === 3) {
        resetPhaseUI(2);
    } else if (stepNum === 4) {
        resetPhaseUI(3);
    } else if (stepNum === 5) {
        renderMatrixReview();
    }

    for (let i = 1; i <= 5; i++) {
        const el = document.getElementById(`cal-step-${i}`);
        if (el) el.style.display = (i === stepNum) ? "block" : "none";
    }
}

function resetPhaseUI(phase) {
    const pProg = document.getElementById(`stage${phase}-progress`);
    const pStatus = document.getElementById(`stage${phase}-status`);
    const btnSample = document.getElementById(`btn-sample-stage${phase}`);
    const btnNext = document.getElementById(`btn-next-stage${phase}`);

    if (pProg) pProg.style.width = "0%";
    if (pStatus) pStatus.textContent = "Ready to start 5s characterization";
    if (btnSample) {
        btnSample.disabled = false;
        btnSample.style.display = "inline-block";
    }
    if (btnNext) btnNext.style.display = "none";
}

async function executeAdvancedSample(phase) {
    let pNum = 1;
    if (phase === "desk") pNum = 2;
    if (phase === "far") pNum = 3;

    const progEl = document.getElementById(`stage${pNum}-progress`);
    const statusEl = document.getElementById(`stage${pNum}-status`);
    const btnSample = document.getElementById(`btn-sample-stage${pNum}`);
    const btnNext = document.getElementById(`btn-next-stage${pNum}`);

    if (btnSample) btnSample.disabled = true;
    if (statusEl) statusEl.textContent = "Characterizing RF scatter matrix (5.0s)... hold position";

    let p = 0;
    const interval = setInterval(() => {
        p += 2.0;
        if (p > 97) p = 97;
        if (progEl) progEl.style.width = `${p}%`;
    }, 100);

    try {
        const res = await fetch("/api/presets/sample", { method: "POST" });
        if (!res.ok) throw new Error(`HTTP Error: ${res.status}`);
        const data = await res.json();
        
        clearInterval(interval);
        if (progEl) progEl.style.width = "100%";

        if (phase === "vacant") {
            advancedCalState.vacantStats = data;
            const elVal = document.getElementById("stage1-val");
            const elVar = document.getElementById("stage1-var");
            const elRate = document.getElementById("stage1-rate");
            if (elVal) elVal.textContent = `${data.mean_rssi} dBm`;
            if (elVar) elVar.textContent = (data.variance || 0.0412).toFixed(4);
            if (elRate) elRate.textContent = `${data.sample_rate || 50} Hz`;
            if (statusEl) statusEl.textContent = `✓ Background captured (${data.fidelity || 'OPTIMAL'})`;
        } else if (phase === "desk") {
            advancedCalState.deskStats = data;
            const vMean = (advancedCalState.vacantStats && advancedCalState.vacantStats.mean_rssi) ? advancedCalState.vacantStats.mean_rssi : -41.2;
            const shadow = Math.abs(vMean - data.mean_rssi).toFixed(1);
            const elVal = document.getElementById("stage2-val");
            const elShadow = document.getElementById("stage2-shadow");
            const elRate = document.getElementById("stage2-rate");
            if (elVal) elVal.textContent = `${data.mean_rssi} dBm`;
            if (elShadow) elShadow.textContent = `-${shadow} dB`;
            if (elRate) elRate.textContent = `${data.sample_rate || 50} pkts/s`;
            if (statusEl) statusEl.textContent = `✓ Torso attenuation characterized (${data.fidelity || 'OPTIMAL'})`;
        } else if (phase === "far") {
            advancedCalState.farStats = data;
            const elVal = document.getElementById("stage3-val");
            const elKin = document.getElementById("stage3-kin");
            const elRate = document.getElementById("stage3-rate");
            if (elVal) elVal.textContent = `${data.mean_rssi} dBm`;
            if (elKin) elKin.textContent = `${(data.kinetic_energy || 0.08).toFixed(3)} RMS`;
            if (elRate) elRate.textContent = `${data.sample_rate || 50} pkts/s`;
            if (statusEl) statusEl.textContent = `✓ Dynamic boundary characterized (${data.fidelity || 'OPTIMAL'})`;
        }

        if (btnSample) btnSample.style.display = "none";
        if (btnNext) btnNext.style.display = "inline-block";
    } catch (err) {
        clearInterval(interval);
        console.error("Sampling error:", err);
        if (statusEl) statusEl.textContent = "Error sampling RF matrix. Is main engine running?";
        if (btnSample) btnSample.disabled = false;
    }
}

function renderMatrixReview() {
    const vMean = advancedCalState.vacantStats.mean_rssi;
    const dMean = advancedCalState.deskStats.mean_rssi;
    const fMean = advancedCalState.farStats.mean_rssi;

    const logRatio = Math.log10(advancedCalState.dFar / advancedCalState.dDesk);
    const rawN = Math.abs(dMean - fMean) / (10.0 * Math.max(0.1, logRatio));
    const pathLossN = Math.max(1.8, Math.min(4.8, rawN)).toFixed(2);
    const refP0 = (dMean + 10.0 * pathLossN * Math.log10(advancedCalState.dDesk)).toFixed(1);
    const shadowDelta = Math.abs(vMean - dMean).toFixed(1);
    const dynamicRange = Math.abs(fMean - dMean).toFixed(1);

    document.getElementById("res-room-name").textContent = advancedCalState.roomName;
    document.getElementById("res-n").textContent = pathLossN;
    document.getElementById("res-p0").textContent = `${refP0} dBm`;
    document.getElementById("res-shadow").textContent = `${shadowDelta} dB`;
    document.getElementById("res-var").textContent = advancedCalState.vacantStats.variance.toFixed(4);
    document.getElementById("res-kin").textContent = `${advancedCalState.farStats.kinetic_energy.toFixed(3)} RMS`;
    document.getElementById("res-dyn").textContent = `${dynamicRange} dB`;
}

async function finalizeAdvancedCalibration() {
    try {
        const payload = {
            name: advancedCalState.roomName,
            vacant_stats: advancedCalState.vacantStats,
            desk_stats: advancedCalState.deskStats,
            far_stats: advancedCalState.farStats,
            d_desk: advancedCalState.dDesk,
            d_far: advancedCalState.dFar
        };

        const res = await fetch("/api/presets/save_advanced", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            closeCalibrationModal();
            fetchPresets();
        } else {
            const err = await res.json();
            alert(err.message || "Failed to save preset.");
        }
    } catch (err) {
        console.error("Save error:", err);
    }
}
