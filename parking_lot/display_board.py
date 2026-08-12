"""
display_board.py — DisplayBoard: shows real-time spot availability per floor
"""

from __future__ import annotations
from parking_lot.enums import SpotType
from parking_lot.spot import ParkingSpot


class DisplayBoard:
    def __init__(self, floor_number: int):
        self.floor_number = floor_number

    def display(self, spots: list[ParkingSpot]):
        label = "Ground Floor 1" if self.floor_number == 1 else f"Floor {self.floor_number}"
        print(f"\n{'═'*48}")
        print(f"  📋 DISPLAY BOARD — {label}")
        print(f"{'═'*48}")

        if not spots:
            print("  ℹ  No parking spots configured for this floor yet.")
            print(f"{'═'*48}")
            return

        counts: dict[SpotType, dict[str, int]] = {}
        for spot in spots:
            if spot.spot_type not in counts:
                counts[spot.spot_type] = {"total": 0, "available": 0}
            counts[spot.spot_type]["total"] += 1
            if spot.is_available:
                counts[spot.spot_type]["available"] += 1

        for stype, data in sorted(counts.items(), key=lambda item: item[0].value):
            filled = data["total"] - data["available"]
            bar    = "█" * data["available"] + "░" * filled
            print(f"  {stype.value:25s}: {data['available']:3d}/{data['total']:3d}  [{bar}]")

        print(f"{'═'*48}")
