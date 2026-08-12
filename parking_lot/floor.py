from __future__ import annotations
import threading
from typing import Optional
from parking_lot.enums import SpotType
from parking_lot.spot import ParkingSpot
from parking_lot.display_board import DisplayBoard


class ParkingFloor:
    def __init__(self, floor_number: int):
        self.floor_number  = floor_number
        self.spots: list[ParkingSpot] = []
        self.display_board = DisplayBoard(floor_number)
        self._lock         = threading.Lock()

    @property
    def floor_label(self) -> str:
        return "Ground Floor 1" if self.floor_number == 1 else f"Floor {self.floor_number}"

    def add_spot(self, spot: ParkingSpot):
        with self._lock:
            self.spots.append(spot)

    def remove_spot(self, spot_number: str) -> bool:
        with self._lock:
            for i, spot in enumerate(self.spots):
                if spot.spot_number == spot_number:
                    if not spot.is_available:
                        print(f"  ⚠ Spot {spot_number} is occupied; cannot remove.")
                        return False
                    self.spots.pop(i)
                    return True
        return False

    def find_nearest_spot(self, compatible: list[SpotType]) -> Optional[ParkingSpot]:
        """Return first available spot matching preference order."""
        with self._lock:
            for preferred in compatible:
                for spot in self.spots:
                    if spot.spot_type == preferred and spot.is_available:
                        return spot
        return None

    def show_display(self):
        self.display_board.display(self.spots)

    def availability_summary(self) -> dict[SpotType, tuple[int, int]]:
        """Returns {SpotType: (available, total)} for this floor."""
        summary: dict[SpotType, tuple[int, int]] = {}
        for spot in self.spots:
            avail, total = summary.get(spot.spot_type, (0, 0))
            summary[spot.spot_type] = (
                avail + (1 if spot.is_available else 0),
                total + 1,
            )
        return summary
