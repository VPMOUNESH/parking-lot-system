"""
spot.py — ParkingSpot: represents a single parking space with thread-safe state
"""

from __future__ import annotations
import threading
from parking_lot.enums import SpotType


class ParkingSpot:
    def __init__(self, spot_id: str, spot_number: str, spot_type: SpotType):
        self.spot_id      = spot_id
        self.spot_number  = spot_number
        self.spot_type    = spot_type
        self.is_available = True
        self._lock        = threading.Lock()

    def occupy(self) -> bool:
        """Atomically mark spot as occupied. Returns True if successful."""
        with self._lock:
            if self.is_available:
                self.is_available = False
                return True
            return False

    def free(self):
        """Mark spot as available again."""
        with self._lock:
            self.is_available = True

    def __str__(self):
        status = "FREE" if self.is_available else "OCCUPIED"
        return (f"  Spot [{self.spot_number}] | "
                f"{self.spot_type.value} | {status}")
