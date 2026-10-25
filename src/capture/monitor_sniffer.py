"""Passive 802.11 Radiotap sniffer in monitor mode with Multi-Device Mesh Harvesting."""

import logging
import threading
import time
from typing import Optional, Set
from scapy.all import sniff, Dot11, RadioTap
from src.capture.base import BaseCapture

logger = logging.getLogger(__name__)


class MonitorSniffer(BaseCapture):
    def __init__(self, interface: str, target_bssid: Optional[str] = None):
        super().__init__()
        self.interface = interface
        self.target_bssid = target_bssid.lower() if target_bssid else None
        self._thread: Optional[threading.Thread] = None
        self.active_clients: Set[str] = set()
        self.packet_count: int = 0
        self._last_stats_log: float = time.time()

    def _packet_handler(self, pkt) -> None:
        if not self.is_running:
            return

        if pkt.haslayer(RadioTap) and pkt.haslayer(Dot11):
            dot11 = pkt[Dot11]
            addr1 = str(getattr(dot11, "addr1", "") or "").lower()
            addr2 = str(getattr(dot11, "addr2", "") or "").lower()
            addr3 = str(getattr(dot11, "addr3", "") or "").lower()

            # Multi-Device Mesh Harvesting:
            # Capture all transmissions originating from the router downstairs (addr2 == target_bssid)
            # or addressed via the router (addr3 == target_bssid) to ANY device in the house.
            if self.target_bssid:
                is_router_tx = (addr2 == self.target_bssid or addr3 == self.target_bssid)
                if not is_router_tx:
                    return

                # Track destination devices being harvested
                if addr1 and addr1 != self.target_bssid and addr1 != "ff:ff:ff:ff:ff:ff":
                    if addr1 not in self.active_clients:
                        self.active_clients.add(addr1)
                        logger.info(f"[MESH HARVEST] New household link active: {addr1} (Total Mesh Nodes: {len(self.active_clients)})")

            # Extract hardware antenna signal in dBm
            try:
                dbm = pkt[RadioTap].dBm_AntSignal
                if dbm is not None and -100 <= dbm <= 0:
                    self.packet_count += 1
                    self.put_sample(time.time(), float(dbm))
            except AttributeError:
                pass

        # Periodic harvest rate logging (every 15 seconds)
        now = time.time()
        if now - self._last_stats_log >= 15.0:
            logger.info(f"[MESH STATS] Ingested {self.packet_count} frames across {len(self.active_clients)} active household client paths.")
            self._last_stats_log = now

    def _sniff_loop(self) -> None:
        logger.info(f"Multi-Device Mesh Sniffer started on {self.interface} (Router BSSID: {self.target_bssid or 'ALL'})")
        try:
            sniff(
                iface=self.interface,
                prn=self._packet_handler,
                store=False,
                stop_filter=lambda _: not self.is_running,
            )
        except Exception as e:
            logger.error(f"Error in monitor sniffer: {e}")
            self.is_running = False

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._sniff_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        logger.info("Monitor sniffer stopped.")
