#!/usr/bin/env python3
"""CLI utility to check interface status, driver mode, and routing."""

import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings


def run_cmd(cmd: str) -> str:
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return res.stdout.strip()


def main():
    print("=" * 60)
    print("  Wi-Fi Interface & Environment Diagnostic")
    print("=" * 60)

    iface = settings.WIFI_INTERFACE
    print(f"[*] Target Interface: {iface}")
    print(f"[*] Target Router IP: {settings.ROUTER_IP}")
    print(f"[*] Target BSSID:     {settings.ROUTER_BSSID or 'Not Set'}")
    print(f"[*] Capture Mode:     {settings.CAPTURE_MODE.upper()}")

    # 1. Check if interface exists in kernel
    link_info = run_cmd(f"ip link show {iface}")
    if not link_info:
        print(f"[-] ERROR: Interface '{iface}' not found in 'ip link'!")
        sys.exit(1)
    print(f"[+] Interface '{iface}' exists.")

    # 2. Check wireless mode
    iw_info = run_cmd(f"iw dev {iface} info")
    print(f"[*] Interface state:\n    {iw_info.splitlines()[1] if len(iw_info.splitlines()) > 1 else 'UP'}")

    # 3. Check monitor mode capability
    modes = run_cmd("iw list")
    if "monitor" in modes:
        print("[+] Wireless chipset supports MONITOR mode.")
    else:
        print("[-] Wireless chipset reports NO monitor mode support.")

    # 4. Check Root Permissions
    if os.geteuid() == 0:
        print("[+] Running with ROOT privileges (Required for raw sockets / monitor mode).")
    else:
        print("[!] WARNING: Not running as root. You will need 'sudo' for monitor/raw sockets.")

    print("\nDiagnostic complete. System ready to run.")


if __name__ == "__main__":
    main()
