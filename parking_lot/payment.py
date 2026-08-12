"""
payment.py — Payment entity, PaymentProcessor strategy hierarchy (Cash / Card / UPI)
"""

from __future__ import annotations
import uuid
import math
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from parking_lot.enums import PaymentMethod, PaymentStatus, HOURLY_RATES

if TYPE_CHECKING:
    from parking_lot.ticket import ParkingTicket


class Payment:
    def __init__(self, ticket: "ParkingTicket", method: PaymentMethod):
        self.payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        self.ticket     = ticket
        self.method     = method
        self.status     = PaymentStatus.PENDING
        self.amount: float              = 0.0
        self.paid_at: Optional[datetime] = None

    def calculate_amount(self) -> float:
        """Exact-time billing: charge per fraction of hour actually used."""
        mins  = self.ticket.duration_minutes()
        hours = math.ceil(mins * 10) / 10          # keep one decimal place
        if hours == 0:
            hours = 1 / 6                           # minimum ~10 min charge
        rate        = HOURLY_RATES[self.ticket.vehicle.vehicle_type]
        self.amount = round(rate * hours, 2)
        return self.amount

    def process(self) -> bool:
        self.status  = PaymentStatus.COMPLETED
        self.paid_at = datetime.now()
        self.ticket.mark_paid()
        return True

    def refund(self):
        if self.status == PaymentStatus.COMPLETED:
            self.status = PaymentStatus.REFUNDED

    def receipt(self) -> str:
        mins        = self.ticket.duration_minutes()
        hrs         = int(mins // 60)
        rem         = int(mins % 60)
        duration_str = f"{hrs}h {rem}m"
        exit_str    = (self.ticket.exit_time.strftime('%d-%m-%Y %I:%M %p')
                       if self.ticket.exit_time else "N/A")
        return (
            f"\n{'═'*48}\n"
            f"  🧾 PAYMENT RECEIPT\n"
            f"{'═'*48}\n"
            f"  Payment ID    : {self.payment_id}\n"
            f"  Ticket ID     : {self.ticket.ticket_id}\n"
            f"  Vehicle No    : {self.ticket.vehicle.vehicle_number}\n"
            f"  Entry         : {self.ticket.entry_time.strftime('%d-%m-%Y %I:%M %p')}\n"
            f"  Exit          : {exit_str}\n"
            f"  Duration      : {duration_str}\n"
            f"  Rate          : ₹{HOURLY_RATES[self.ticket.vehicle.vehicle_type]:.0f}/hr\n"
            f"  Amount        : ₹{self.amount:.2f}\n"
            f"  Method        : {self.method.value}\n"
            f"  Status        : {self.status.value}\n"
            f"{'═'*48}"
        )


# ── Strategy: Payment Processors ─────────────────────────────────────────────

class PaymentProcessor(ABC):
    """Abstract strategy — implement pay() to add a new payment method."""

    @abstractmethod
    def pay(self, payment: Payment) -> bool:
        pass


class CashProcessor(PaymentProcessor):
    def pay(self, payment: Payment) -> bool:
        print(f"  💵 Cash payment of ₹{payment.amount:.2f} accepted.")
        return payment.process()


class CardProcessor(PaymentProcessor):
    def pay(self, payment: Payment) -> bool:
        print(f"  💳 Card payment of ₹{payment.amount:.2f} processed.")
        return payment.process()


class UPIProcessor(PaymentProcessor):
    def pay(self, payment: Payment) -> bool:
        print(f"  📱 UPI payment of ₹{payment.amount:.2f} successful.")
        return payment.process()


PAYMENT_PROCESSORS: dict[PaymentMethod, PaymentProcessor] = {
    PaymentMethod.CASH: CashProcessor(),
    PaymentMethod.CARD: CardProcessor(),
    PaymentMethod.UPI:  UPIProcessor(),
}
