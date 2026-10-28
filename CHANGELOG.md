# Changelog

All notable changes, bug fixes, and feature additions for the Wi-Fi RF Presence Radar project.

## [v1.4.0]

### Added
- **Native Desktop Application Launcher (`desktop.py`):** Added a lightweight native window entry point powered by `pywebview` running over WebKitGTK, launching the dashboard directly as a standalone desktop utility while maintaining full web browser compatibility.
- **Process Group Isolation for Engine Lifecycle:** Configured `subprocess.Popen` with process group assignment (`os.setsid`) in `desktop.py` along with synchronous port health polling, ensuring clean startup synchronization and graceful recursive teardown of the FastAPI/Uvicorn background engine on exit.
- **Single-Line Deployment Scripts:** Added automated one-line setup runbooks for onboarding:
  - `SETUP_ARCH.md`: Automates pacman networking dependencies (`iw`, `iproute2`), virtual environment creation, package installation, and non-root raw packet capability assignment (`setcap cap_net_raw,cap_net_admin=eip`).
  - `SETUP_WINDOWS.md`: Automates PowerShell execution policy handling, venv setup, dependencies, and environment configuration.

### Fixed
- **WebKitGTK Wayland & DMA-Buf Rendering Crash:** Resolved protocol errors on Arch Linux / Hyprland by setting environment overrides (`WEBKIT_DISABLE_DMABUF_RENDERER=1`, `WEBKIT_DISABLE_COMPOSITING_MODE=1`, and `GDK_BACKEND="x11,wayland"`) prior to window instantiation.
- **WebKitGTK Missing `localStorage` Exception:** Fixed a fatal `ReferenceError: Can't find variable: localStorage` halting execution in `app.js` under WebKit private/sandboxed sessions by implementing an in-memory `safeStorage` polyfill fallback.
- **Dynamic WebSocket Origin Resolution:** Replaced static host references with dynamic `window.location.host` and protocol detection (`ws://` vs `wss://`), enabling simultaneous WebSocket connectivity across native desktop windows, local browsers, and LAN client access.

---

## [v1.3.0]

### Added
- **Multi-Target Radar Tracking:** Added visual radar blips for secondary and tertiary occupants when `headcount >= 2`. Secondary targets are positioned and rendered dynamically on the circular radar sweep.
- **Through-Wall Isolation:** Implemented a geofence distance filter in `crowd_estimator.py` that separates in-room motion from adjacent room activity (>2.5m). Movement behind drywall is tagged as an exterior target and no longer falsely inflates internal room headcount.
- **In-Browser 3-Phase Calibration Wizard:** Built an interactive web modal replacing the old CLI calibration script:
  - Phase 1: Captures ambient room noise floor and static multipath variance (σ²).
  - Phase 2: Measures direct torso shadow absorption (P₀) while seated at the desk.
  - Phase 3: Profiles maximum kinetic Doppler energy while walking across the room boundary.
- **Propagation Parameter Solver:** Added automated calculation for log-distance path loss exponent ($n$), 1-meter reference power ($P_0$), and torso absorption delta in `presets.py`.
- **Room Preset Manager:** Added support for up to 3 room profiles with live switching via FastAPI endpoints (`/api/presets`, `/api/presets/activate`, `/api/presets/save_advanced`, `/api/presets/delete`).

### Fixed
- **Radar Dot Drifting While Seated:** Added kinetic velocity gating and a seated desk deadband lock in `proximity.py`. When seated and motion is quiet, position locks firmly at ~0.88m and suppresses random $\pm 2\text{ dBm}$ carrier jitter.
- **Headcount Jumps (Over-Triggering to 3):** Re-calibrated variance and kinetic RMS thresholds in `crowd_estimator.py` to match real-world single-person walking vs multi-person cross-scattering.
- **Raw LaTeX Formatting in Modal:** Replaced broken LaTeX tags with clean Unicode labels (`σ²`, `P₀`, `n`) so they render natively in browsers without math engines.
- **Modal Step Navigation Mismatch:** Fixed button ID mismatches in `index.html` and `app.js` that previously threw null reference errors during step transitions.
- **UI Element Cleanup:** Removed orphaned CLI baseline buttons from the dashboard footer.

---

## [v1.2.0]

### Added
- **Auto-Illumination Engine:** Added automatic 50 Hz background packet streaming in `main.py` using `subprocess.Popen` to ping the gateway, with automatic process cleanup on shutdown.
- **Live RSSI Telemetry Buffer:** Connected the WebSocket broadcast pipeline to a sample buffer in `app.py` for real-time sampling during calibration.

### Fixed
- **Zero-Packet Sniffer Drop (Baseband Desync):** Fixed frame capture failure caused by forcing 40 MHz channel width on 2.4 GHz USB adapters. Locked monitor mode to standard 20 MHz Channel 11, restoring packet ingestion (~50 pkts/s).
- **NetworkManager / Hyprland D-Bus Disconnect:** Replaced `systemctl restart NetworkManager` commands with `nmcli device set <iface> managed no/yes`. This prevents breaking the D-Bus connection on Arch Linux / Hyprland / Serpantinum status bars.
- **Syntax Error in `main.py`:** Cleaned up broken regex artifacts and reorganized thread startup and atexit handlers.

---

## [v1.1.0]

### Added
- **Dynamic Threshold Updates:** Added `update_profile()` hook in `proximity.py` to hot-swap calibration values without restarting the ASGI server.
- **Presets Toolbar:** Added visual pill buttons and profile count badges to the dashboard header.

---

## [v1.0.0]

### Initial Release
- Passive 802.11 monitor mode packet sniffer isolated to router BSSID.
- Real-time DSP pipeline: Hampel filter, 0.3–5.0 Hz Butterworth kinetic bandpass, and feature vector extraction.
- Finite state machine for room occupancy (`VACANT`, `ENTERING`, `OCCUPIED`, `EXITING`).
- Log-distance proximity estimator.
- Web dashboard with real-time Chart.js signal graphs and radar canvas via WebSockets.
