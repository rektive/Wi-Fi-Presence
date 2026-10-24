"""Active high-frequency prober measuring transmission latency jitter."""

import logging
import os
import select
import socket
import struct
import threading
import time
from typing import Optional
from src.capture.base import BaseCapture

logger = logging.getLogger(__name__)


def _checksum(source_bytes: bytes) -> int:
    count_to = (len(source_bytes) // 2) * 2
    count = 0
    sum_val = 0
    while count < count_to:
        this_val = source_bytes[count + 1] * 256 + source_bytes[count]
        sum_val = sum_val + this_val
        sum_val = sum_val & 0xFFFFFFFF
        count += 2
    if count_to < len(source_bytes):
        sum_val = sum_val + source_bytes[len(source_bytes) - 1]
        sum_val = sum_val & 0xFFFFFFFF
    sum_val = (sum_val >> 16) + (sum_val & 0xFFFF)
    sum_val = sum_val + (sum_val >> 16)
    answer = ~sum_val
    answer = answer & 0xFFFF
    return answer >> 8 | (answer << 8 & 0xFF00)


class ActiveProber(BaseCapture):
    """Measures sub-millisecond round-trip jitter to the router gateway via raw ICMP."""

    def __init__(self, target_ip: str, rate_hz: int = 50):
        super().__init__()
        self.target_ip = target_ip
        self.rate_hz = rate_hz
        self.interval = 1.0 / rate_hz
        self._thread: Optional[threading.Thread] = None

    def _worker(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.setblocking(False)
        except PermissionError:
            logger.error("Active ICMP Prober requires root privileges (sudo).")
            self.is_running = False
            return

        seq = 0
        pid = os.getpid() & 0xFFFF

        logger.info(f"Active ICMP prober active against {self.target_ip} at {self.rate_hz} Hz")

        while self.is_running:
            loop_start = time.time()
            seq = (seq + 1) & 0xFFFF
            header = struct.pack("!BBHHH", 8, 0, 0, pid, seq)
            payload = struct.pack("!d", loop_start)
            chk = _checksum(header + payload)
            packet = struct.pack("!BBHHH", 8, 0, chk, pid, seq) + payload

            try:
                sock.sendto(packet, (self.target_ip, 1))
            except Exception as e:
                logger.debug(f"ICMP send failed: {e}")

            # Non-blocking receive window
            timeout = min(self.interval * 0.8, 0.02)
            while True:
                ready = select.select([sock], [], [], timeout)
                if not ready[0]:
                    break
                recv_time = time.time()
                recv_packet, _ = sock.recvfrom(1024)
                icmp_header = recv_packet[20:28]
                type_val, _, _, r_id, _ = struct.unpack("!BBHHH", icmp_header)
                if type_val == 0 and r_id == pid:
                    time_sent = struct.unpack("!d", recv_packet[28:36])[0]
                    rtt_ms = (recv_time - time_sent) * 1000.0
                    # Store negative latency so higher variance mirrors attenuation
                    self.put_sample(recv_time, float(rtt_ms))
                    break

            elapsed = time.time() - loop_start
            sleep_time = self.interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        sock.close()
        logger.info("Active prober stopped.")

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
