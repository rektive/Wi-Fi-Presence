const maxDataPoints = 80;
const labels = Array(maxDataPoints).fill("");
const signalData = Array(maxDataPoints).fill(0);
const filteredData = Array(maxDataPoints).fill(0);

const signalCtx = document.getElementById("signalChart").getContext("2d");
const signalChart = new Chart(signalCtx, {
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
});

const dopplerData = Array(maxDataPoints).fill(0);
const dopplerCtx = document.getElementById("dopplerChart").getContext("2d");
const dopplerChart = new Chart(dopplerCtx, {
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
});

// Update UI elements
function updateDashboard(payload) {
    const badge = document.getElementById("state-badge");
    const stateDetail = document.getElementById("state-detail");
    const countVal = document.getElementById("headcount-val");
    const confidenceDetail = document.getElementById("confidence-detail");
    const meter = document.getElementById("kinetic-meter-bar");
    const kineticVal = document.getElementById("kinetic-val");

    badge.innerText = payload.state;
    badge.className = `state-badge state-${payload.state.toLowerCase()}`;

    if (payload.state === "VACANT") {
        stateDetail.innerText = "No movement detected across RF path.";
    } else if (payload.state === "ENTERING") {
        stateDetail.innerText = "Active corridor/doorway entry in progress!";
    } else if (payload.state === "OCCUPIED") {
        stateDetail.innerText = "Sustained human presence active in room.";
    } else if (payload.state === "EXITING") {
        stateDetail.innerText = "Motion decreasing; target exiting perimeter.";
    }

    countVal.innerText = payload.headcount;
    confidenceDetail.innerText = `Scatter Entropy: ${payload.entropy.toFixed(2)} | Var: ${payload.variance.toFixed(4)}`;

    const meterPct = Math.min(Math.max((payload.kinetic_energy / 0.5) * 100, 0), 100);
    meter.style.width = `${meterPct}%`;
    kineticVal.innerText = payload.kinetic_energy.toFixed(3);

    // Update real-time charts
    signalData.push(payload.raw_signal);
    signalData.shift();
    filteredData.push(payload.filtered_signal);
    filteredData.shift();
    signalChart.update();

    dopplerData.push(payload.kinetic_energy);
    dopplerData.shift();
    dopplerChart.update();
}

// WebSocket client with automatic reconnect
function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;
    const socket = new WebSocket(wsUrl);
    const pill = document.getElementById("connection-pill");

    socket.onopen = () => {
        pill.innerText = "Live Connected";
        pill.className = "pill connected";
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
            console.error(e);
        }
    };

    socket.onclose = () => {
        pill.innerText = "Disconnected";
        pill.className = "pill disconnected";
        setTimeout(connectWebSocket, 2000);
    };
}

fetch("/api/status")
    .then(r => r.json())
    .then(data => {
        document.getElementById("net-info").innerText = 
            `Interface: ${data.interface} | Mode: ${data.capture_mode.toUpperCase()} | Rate: ${data.sampling_rate_hz}Hz`;
    });

connectWebSocket();
