from __future__ import annotations
import uuid
from parking_lot.enums import SpotType
from parking_lot.spot import ParkingSpot
from parking_lot.floor import ParkingFloor
from parking_lot.lot import ParkingLot


class Admin:
    MAX_FLOORS          = 5
    MAX_SPOTS_PER_FLOOR = 1000
    SPOT_TYPE_CODES = {
        SpotType.BIKE: "BK",
        SpotType.ELECTRIC_BIKE: "EB",
        SpotType.CAR: "C",
        SpotType.ELECTRIC_CAR: "EC",
        SpotType.TRUCK: "T",
        SpotType.BUS: "B",
    }

    def __init__(self, lot: ParkingLot):
        self.lot = lot

    def _floor_prefix(self, floor_number: int) -> str:
        return "G1" if floor_number == 1 else f"F{floor_number}"

    def _build_spot_number(self, floor_number: int, spot_type: SpotType, numeric: int) -> str:
        prefix = self._floor_prefix(floor_number)
        code = self.SPOT_TYPE_CODES[spot_type]
        return f"{prefix}-{code}{numeric:02d}"

    def _parse_start_number(self, spot_number: str) -> int:
        if spot_number.isdigit():
            return int(spot_number)
        parts = []
        for ch in reversed(spot_number):
            if ch.isdigit():
                parts.append(ch)
            else:
                break
        return int(''.join(reversed(parts))) if parts else 1

    # ── Floor Management ──────────────────────────────────────────────────────

    def add_floor(self, floor_number: int) -> bool:
        if len(self.lot.floors) >= self.MAX_FLOORS:
            print(f"  ⚠ Cannot exceed {self.MAX_FLOORS} floors.")
            return False
        if floor_number in self.lot.floors:
            print(f"  ⚠ Floor {floor_number} already exists.")
            return False
        self.lot.floors[floor_number] = ParkingFloor(floor_number)
        self.lot.save_state()
        print(f"  ✅ Floor {floor_number} added.")
        return True

    def remove_floor(self, floor_number: int) -> bool:
        floor = self.lot.floors.get(floor_number)
        if not floor:
            print(f"  ⚠ Floor {floor_number} not found.")
            return False
        if any(not s.is_available for s in floor.spots):
            print(f"  ⚠ Floor {floor_number} has occupied spots; cannot remove.")
            return False
        del self.lot.floors[floor_number]
        self.lot.save_state()
        print(f"  ✅ Floor {floor_number} removed.")
        return True

    # ── Spot Management ───────────────────────────────────────────────────────

    def add_spot(self, floor_number: int, spot_number: str,
                 spot_type: SpotType, count: int = 1) -> bool:
        floor = self.lot.floors.get(floor_number)
        if not floor:
            print(f"  ⚠ Floor {floor_number} not found.")
            return False
        if count < 1:
            print("  ⚠ Number of spots to add must be at least 1.")
            return False
        remaining_slots = self.MAX_SPOTS_PER_FLOOR - len(floor.spots)
        if remaining_slots <= 0:
            print(f"  ⚠ Floor {floor_number} is at max capacity ({self.MAX_SPOTS_PER_FLOOR} spots).")
            return False
        if count > remaining_slots:
            print(f"  ⚠ Only {remaining_slots} spots can be added to Floor {floor_number}.")
            return False

        start = self._parse_start_number(spot_number)
        for offset in range(count):
            current_number = self._build_spot_number(floor_number, spot_type, start + offset)
            spot_id = f"SP-{uuid.uuid4().hex[:6].upper()}"
            floor.add_spot(ParkingSpot(spot_id, current_number, spot_type))

        self.lot.save_state()
        print(f"  ✅ Added {count} spot(s) to Floor {floor_number} ({spot_type.value}).")
        return True

    def remove_spot(self, floor_number: int, spot_number: str,
                    spot_type: SpotType, count: int = 1) -> bool:
        floor = self.lot.floors.get(floor_number)
        if not floor:
            print(f"  ⚠ Floor {floor_number} not found.")
            return False
        if count < 1:
            print("  ⚠ Number of spots to remove must be at least 1.")
            return False

        target_numbers: list[str]
        if spot_number.isdigit():
            start = int(spot_number)
            target_numbers = [
                self._build_spot_number(floor_number, spot_type, start + offset)
                for offset in range(count)
            ]
        else:
            base_name = spot_number.rstrip("0123456789")
            numeric_suffix = ""
            parts = []
            for ch in reversed(spot_number):
                if ch.isdigit():
                    parts.append(ch)
                else:
                    break
            if parts:
                numeric_suffix = "".join(reversed(parts))
                base_name = spot_number[:-len(numeric_suffix)]
            start = int(numeric_suffix) if numeric_suffix else 1
            target_numbers = [f"{base_name}{start + offset}" for offset in range(count)]

        for target in target_numbers:
            found_spot = next((spot for spot in floor.spots if spot.spot_number == target), None)
            if not found_spot:
                print(f"  ⚠ Spot {target} not found on Floor {floor_number}.")
                return False
            if not found_spot.is_available:
                print(f"  ⚠ Spot {target} is occupied; cannot remove.")
                return False

        for target in target_numbers:
            floor.remove_spot(target)

        self.lot.save_state()
        if count == 1:
            print(f"  ✅ Spot {target_numbers[0]} removed from Floor {floor_number}.")
        else:
            print(f"  ✅ Removed {count} spots starting at {target_numbers[0]} from Floor {floor_number}.")
        return True

    # ── Reports ───────────────────────────────────────────────────────────────

    def view_reports(self):
        self.lot.generate_report()
