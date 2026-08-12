"""
report.py — Report: generates daily summary of vehicles, revenue, and spot usage
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from parking_lot.enums import VehicleType, PaymentStatus

if TYPE_CHECKING:
    from parking_lot.ticket import ParkingTicket
    from parking_lot.payment import Payment


class Report:
    def __init__(self, tickets: list["ParkingTicket"], payments: list["Payment"]):
        self._tickets = tickets
        self._payments = payments

    def daily_report(self, date: Optional[datetime] = None):
        target = date or datetime.now()

        day_tickets = [t for t in self._tickets if t.entry_time.date() == target.date()]
        day_payments = [
            p
            for p in self._payments
            if p.paid_at
            and p.paid_at.date() == target.date()
            and p.status == PaymentStatus.COMPLETED
        ]

        total_revenue = sum(p.amount for p in day_payments)

        print(f"\n{'═' * 52}")
        print(f"  📊 DAILY REPORT — {target.strftime('%d %B %Y')}")
        print(f"{'═' * 52}")
        print(f"  Vehicles Parked   : {len(day_tickets)}")
        print(f"  Completed Payments: {len(day_payments)}")
        print(f"  Total Revenue     : ₹{total_revenue:.2f}")

        vehicle_counts: dict[VehicleType, int] = {}
        for t in day_tickets:
            vehicle_counts[t.vehicle.vehicle_type] = (
                vehicle_counts.get(t.vehicle.vehicle_type, 0) + 1
            )
        if vehicle_counts:
            print(f"\n  Breakdown by Vehicle Type:")
            for vt, cnt in vehicle_counts.items():
                bar = "■" * cnt
                print(f"    {vt.value:20s}: {cnt:3d}  {bar}")

        print(f"{'═' * 52}")
