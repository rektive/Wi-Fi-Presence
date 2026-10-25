"""Passive 802.11 Radiotap sniffer in monitor mode locked strictly to router downlink."""

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

        if pkt.haslayer(RadioTap) and pkt.haslayer(Dot11):
            dot11 = pkt[Dot11]
            
            # STRICT DOWNLINK FILTER:
            # In 802.11 frames, addr2 is the hardware Transmitter Address (TA).
            # We ONLY accept frames physically transmitted by the downstairs router.
            # This completely rejects local PC uplink packets (-25 dBm) that corrupt distance calculations.
            if self.target_bssid:
                transmitter = str(getattr(dot11, "addr2", "") or "").lower()
                if transmitter != self.target_bssid:
                    return

            try:
                dbm = pkt[RadioTap].dBm_AntSignal
                if dbm is not None and -100 <= dbm <= 0:
                    self.put_sample(time.time(), float(dbm))
            except AttributeError:
                pass

    def _sniff_loop(self) -> None:
        logger.info(f"Downlink-Isolated Sniffer active on {self.interface} (Router TA: {self.target_bssid})")
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
