"""Application configuration loaded from environment variables and defaults."""

from pathlib import Path
from typing import Literal, Optional
import re
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base Paths
    ROOT_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    DATA_RAW_DIR: Path = BASE_DIR / "data" / "raw"
    DATA_PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    MODELS_DIR: Path = BASE_DIR / "models"
    
    BASELINE_STATE_PATH: Path = MODELS_DIR / "baseline_state.json"
    HEADCOUNT_MODEL_PATH: Path = MODELS_DIR / "headcount_model.pkl"

    # Radio and Ingestion Config
    WIFI_INTERFACE: str = Field(default="wlan0", description="Target Wi-Fi interface name")
    ROUTER_IP: str = Field(default="192.168.1.1", description="Gateway IP address")
    ROUTER_BSSID: Optional[str] = Field(
        default=None,
        description="Router MAC address (BSSID) for hardware-level Radiotap filtering",
    )
    CAPTURE_MODE: Literal["monitor", "active"] = Field(
        default="monitor",
        description="Ingestion mechanism: passive monitor mode vs active packet generation",
    )

    # Signal & Sampling Characteristics
    SAMPLING_RATE_HZ: int = Field(default=50, ge=10, le=200)
    WINDOW_SIZE_SAMPLES: int = Field(default=100, ge=20, le=1000)
    SENSITIVITY_FACTOR: float = Field(default=2.5, gt=0.1)

    # Digital Signal Processing (DSP) Filters
    BANDPASS_LOW_HZ: float = Field(default=0.3, gt=0.0)
    BANDPASS_HIGH_HZ: float = Field(default=5.0, gt=0.0)
    BUTTERWORTH_ORDER: int = Field(default=4, ge=1, le=8)
    HAMPEL_WINDOW: int = Field(default=7, ge=3)
    HAMPEL_N_SIGMA: float = Field(default=3.0, gt=0.5)

    # Server & Networking
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8000
    DEBUG: bool = False

    @field_validator("ROUTER_BSSID")
    @classmethod
    def validate_and_normalize_bssid(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        cleaned = v.strip().lower()
        if not re.match(r"^([0-9a-f]{2}[:-]){5}([0-9a-f]{2})$", cleaned):
            raise ValueError(f"Invalid BSSID / MAC address format: {v}")
        return cleaned.replace("-", ":")

    @field_validator("BANDPASS_HIGH_HZ")
    @classmethod
    def validate_nyquist(cls, v: float, info) -> float:
        fs = info.data.get("SAMPLING_RATE_HZ", 50)
        nyquist = fs / 2.0
        if v >= nyquist:
            raise ValueError(
                f"BANDPASS_HIGH_HZ ({v}) must be strictly lower than the Nyquist frequency ({nyquist})"
            )
        return v


# Singleton instance accessible throughout the project
settings = Settings()

# Ensure directories exist upon initial import
settings.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
settings.MODELS_DIR.mkdir(parents=True, exist_ok=True)