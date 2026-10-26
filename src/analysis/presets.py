"""Advanced Room RF Multi-Path Calibration Engine & Preset Store."""
import json
import math
import pathlib
import time
from typing import Dict, Any, Optional

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
PRESETS_FILE = ROOT_DIR / "presets.json"
PROFILE_FILE = ROOT_DIR / "profile.json"

DEFAULT_PRESET = {
    "name": "Default",
    "desk_mean": -49.07,
    "away_mean": -38.09,
    "vacant_mean": -41.20,
    "vacant_variance": 0.0412,
    "ref_rssi_1m": -48.00,
    "path_loss_n": 3.20,
    "shadow_delta_db": 7.87,
    "kinetic_threshold": 0.045,
    "quality_score": 98,
    "description": "Factory Calibrated Baseline",
    "created_at": "Default"
}

def init_presets() -> Dict[str, Any]:
    if PRESETS_FILE.exists():
        try:
            data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
            if "presets" in data and "Default" in data["presets"]:
                return data
        except Exception:
            pass

    initial_data = {
        "active": "Default",
        "presets": {
            "Default": DEFAULT_PRESET
        }
    }
    save_presets(initial_data)
    return initial_data

def load_presets() -> Dict[str, Any]:
    if not PRESETS_FILE.exists():
        return init_presets()
    try:
        return json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return init_presets()

def save_presets(data: Dict[str, Any]) -> None:
    PRESETS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    active_name = data.get("active", "Default")
    active_prof = data.get("presets", {}).get(active_name, DEFAULT_PRESET)
    PROFILE_FILE.write_text(json.dumps(active_prof, indent=2), encoding="utf-8")

def get_active_profile() -> Dict[str, Any]:
    data = load_presets()
    active = data.get("active", "Default")
    return data.get("presets", {}).get(active, DEFAULT_PRESET)

def set_active_preset(name: str) -> Optional[Dict[str, Any]]:
    data = load_presets()
    if name in data.get("presets", {}):
        data["active"] = name
        save_presets(data)
        return data["presets"][name]
    return None

def compute_rf_matrix(vacant_stats: dict, desk_stats: dict, far_stats: dict, d_desk=0.9, d_far=2.4) -> dict:
    """Solves analytical RF path loss exponent, reference power, and multipath scattering parameters."""
    v_mean = vacant_stats.get("mean_rssi", -41.2)
    v_var = max(0.005, vacant_stats.get("variance", 0.041))
    d_mean = desk_stats.get("mean_rssi", -49.0)
    f_mean = far_stats.get("mean_rssi", -38.5)
    f_kin = far_stats.get("kinetic_energy", 0.12)

    # Torso RF absorption shadow depth
    shadow_delta = round(abs(v_mean - d_mean), 2)

    # Solve Log-Distance Path Loss Exponent: RSSI(d) = P0 - 10*n*log10(d)
    log_ratio = math.log10(d_far / d_desk)
    rssi_diff = abs(d_mean - f_mean)
    raw_n = (rssi_diff / (10.0 * max(0.1, log_ratio))) if log_ratio > 0 else 3.0
    # Bound inside realistic physical indoor boundary limits
    path_loss_n = round(max(1.8, min(4.8, raw_n)), 2)

    # Calibrated Reference RSSI at 1.0m
    ref_rssi_1m = round(d_mean + (10.0 * path_loss_n * math.log10(d_desk)), 2)

    # Adaptive kinetic motion threshold (3x vacant noise energy)
    kinetic_thresh = round(max(0.025, min(0.35, f_kin * 0.35)), 3)

    # Calibration Fidelity Quality (0-100%)
    p_rate = min(vacant_stats.get("sample_rate", 50), desk_stats.get("sample_rate", 50), far_stats.get("sample_rate", 50))
    rate_score = min(50.0, (p_rate / 45.0) * 50.0)
    var_score = 30.0 if v_var < 0.25 else 15.0
    contrast_score = 20.0 if shadow_delta >= 4.0 else 10.0
    quality = int(round(min(100.0, rate_score + var_score + contrast_score)))

    return {
        "desk_mean": round(d_mean, 2),
        "away_mean": round(f_mean, 2),
        "vacant_mean": round(v_mean, 2),
        "vacant_variance": round(v_var, 6),
        "ref_rssi_1m": ref_rssi_1m,
        "path_loss_n": path_loss_n,
        "shadow_delta_db": shadow_delta,
        "kinetic_threshold": kinetic_thresh,
        "quality_score": quality
    }

def add_advanced_preset(name: str, rf_metrics: dict) -> bool:
    data = load_presets()
    presets = data.get("presets", {})
    if len(presets) >= 3 and name not in presets:
        return False

    rf_metrics["name"] = name
    rf_metrics["description"] = f"RF Profile (n={rf_metrics['path_loss_n']}, P0={rf_metrics['ref_rssi_1m']} dBm)"
    rf_metrics["created_at"] = time.strftime("%Y-%m-%d %H:%M")

    presets[name] = rf_metrics
    data["active"] = name
    save_presets(data)
    return True

def delete_preset(name: str) -> bool:
    if name == "Default":
        return False
    data = load_presets()
    presets = data.get("presets", {})
    if name in presets:
        del presets[name]
        if data.get("active") == name:
            data["active"] = "Default"
        save_presets(data)
        return True
    return False
