"""Passive 802.11 Radiotap sniffer in monitor mode using Scapy."""

import logging
import threading
import time
from typing import Optional
from scapy.all import sniff, Dot11, RadioTap
from src.capture.base import BaseCapture

logger = logging.getLogger(__name__)


class MonitorSniffer(BaseCapture):
    def __init__(self, interface: str, target_bssid: Optional[str] = None):
        super().__init__()
        self.interface = interface
        self.target_bssid = target_bssid.lower() if target_bssid else None
        self._thread: Optional[threading.Thread] = None

    def _packet_handler(self, pkt) -> None:
        if not self.is_running:
            return

        if pkt.haslayer(RadioTap):
            # Check target BSSID filter if configured
            if self.target_bssid and pkt.haslayer(Dot11):
                addr1 = getattr(pkt[Dot11], "addr1", "")
                addr2 = getattr(pkt[Dot11], "addr2", "")
                addr3 = getattr(pkt[Dot11], "addr3", "")
                addresses = [str(a).lower() for a in (addr1, addr2, addr3) if a]
                if self.target_bssid not in addresses:
                    return

            # Extract hardware antenna signal in dBm
            try:
                dbm = pkt[RadioTap].dBm_AntSignal
                if dbm is not None and -100 <= dbm <= 0:
                    self.put_sample(time.time(), float(dbm))
            except AttributeError:
                pass

    def _sniff_loop(self) -> None:
        logger.info(f"Monitor sniffer started on {self.interface} (Target: {self.target_bssid or 'ALL'})")
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
