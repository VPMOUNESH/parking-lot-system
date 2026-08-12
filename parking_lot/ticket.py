"""
ticket.py — ParkingTicket: generated on vehicle entry, tracks status and timing
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from parking_lot.enums import TicketStatus

if TYPE_CHECKING:
    from parking_lot.vehicle import Vehicle
    from parking_lot.spot import ParkingSpot


class ParkingTicket:
    def __init__(self, vehicle: "Vehicle", spot: "ParkingSpot", floor_number: int):
        self.ticket_id    = f"TKT-{uuid.uuid4().hex[:8].upper()}"
        self.vehicle      = vehicle
        self.spot         = spot
        self.floor_number = floor_number
        self.entry_time: datetime          = datetime.now()
        self.exit_time: Optional[datetime] = None
        self.status: TicketStatus          = TicketStatus.ACTIVE

    @property
    def floor_label(self) -> str:
        return "Ground Floor 1" if self.floor_number == 1 else f"Floor {self.floor_number}"

    def mark_paid(self):
        self.status    = TicketStatus.PAID
        self.exit_time = datetime.now()

    def mark_lost(self):
        self.status = TicketStatus.LOST

    def duration_minutes(self) -> float:
        end   = self.exit_time if self.exit_time else datetime.now()
        delta = end - self.entry_time
        return delta.total_seconds() / 60

    def __str__(self):
        return (
            f"\n{'─'*48}\n"
            f"  🎫 PARKING TICKET\n"
            f"{'─'*48}\n"
            f"  Ticket ID     : {self.ticket_id}\n"
            f"  Vehicle No    : {self.vehicle.vehicle_number}\n"
            f"  Vehicle Type  : {self.vehicle.vehicle_type.value}\n"
            f"  Owner         : {self.vehicle.owner_name}\n"
            f"  Entry Time    : {self.entry_time.strftime('%d-%m-%Y %I:%M:%S %p')}\n"
            f"  Spot Number   : {self.spot.spot_number}\n"
            f"  Floor         : {self.floor_label}\n"
            f"  Status        : {self.status.value}\n"
            f"{'─'*48}"
        )
