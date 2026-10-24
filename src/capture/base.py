"""Abstract base class for RF and packet ingestion engines."""

import abc
import queue
from typing import Optional, Tuple


class BaseCapture(abc.ABC):
    def __init__(self, sample_queue_size: int = 2000):
        self.sample_queue: queue.Queue[Tuple[float, float]] = queue.Queue(maxsize=sample_queue_size)
        self.is_running: bool = False

    @abc.abstractmethod
    def start(self) -> None:
        """Starts the capture background thread or process."""
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        """Stops the capture worker cleanly."""
        pass

    def get_sample(self, timeout: float = 0.1) -> Optional[Tuple[float, float]]:
        """Retrieves the next (timestamp, signal_value) pair from the queue."""
        try:
            return self.sample_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def put_sample(self, timestamp: float, value: float) -> None:
        """Pushes a sample into the buffer, dropping old frames if saturated."""
        if self.sample_queue.full():
            try:
                self.sample_queue.get_nowait()
            except queue.Empty:
                pass
        self.sample_queue.put((timestamp, value))
