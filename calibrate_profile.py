#!/usr/bin/env python3
import time
import json
import pathlib
import numpy as np
from scapy.all import sniff, RadioTap, Dot11
from config.settings import settings

print("==================================================")
print("   Wi-Fi Presence: 2-Point Physical Calibrator   ")
print("==================================================")

interface = settings.WIFI_INTERFACE
router_bssid = settings.ROUTER_BSSID.lower()

def collect_samples(label: str, duration_sec: int = 5):
    print(f"\n>>> SAMPLING [{label}] for {duration_sec} seconds...")
    samples = []
    start = time.time()
    
    def pkt_cb(pkt):
        if pkt.haslayer(RadioTap) and pkt.haslayer(Dot11):
            dot11 = pkt[Dot11]
            ta = str(getattr(dot11, "addr2", "") or "").lower()
            if ta == router_bssid:
                try:
                    dbm = pkt[RadioTap].dBm_AntSignal
                    if dbm is not None and -100 <= dbm <= 0:
                        samples.append(float(dbm))
                except AttributeError:
                    pass

    sniff(iface=interface, prn=pkt_cb, timeout=duration_sec, store=False)
    
    if len(samples) < 20:
        print(f"Warning: Only collected {len(samples)} packets. Ensure router ping is active.")
    
    arr = np.array(samples) if samples else np.array([-48.0])
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))
    print(f"    Result -> Mean RSSI: {mean_val:.2f} dBm | StDev: {std_val:.2f} dB | Packets: {len(samples)}")
    return {"mean": mean_val, "std": std_val, "samples": len(samples)}

# Point 1: At Desk
input("\n[STEP 1]: Sit normally AT YOUR DESK (< 1m from adapter), then press ENTER...")
desk_profile = collect_samples("AT DESK (< 1m)", duration_sec=6)

# Point 2: Perimeter
input("\n[STEP 2]: Stand AWAY FROM DESK (2m - 2.5m near room perimeter), then press ENTER...")
away_profile = collect_samples("PERIMETER (2m - 2.5m)", duration_sec=6)

profile_data = {
    "desk_mean": desk_profile["mean"],
    "desk_std": max(desk_profile["std"], 0.2),
    "away_mean": away_profile["mean"],
    "away_std": max(away_profile["std"], 0.1),
    "timestamp": time.time()
}

out_path = pathlib.Path.home() / "Coding/presence/Wi-Fi-Presence/profile.json"
out_path.write_text(json.dumps(profile_data, indent=4), encoding="utf-8")
print("\n✓ Calibration saved successfully to profile.json!")
print(f"  Desk RSSI: {profile_data['desk_mean']:.1f} dBm (±{profile_data['desk_std']:.2f})")
print(f"  Away RSSI: {profile_data['away_mean']:.1f} dBm (±{profile_data['away_std']:.2f})")
