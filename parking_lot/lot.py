"""
lot.py — ParkingLot: Singleton, thread-safe core system (entry, exit, lookup)
"""

from __future__ import annotations
import threading
import uuid
from datetime import datetime
from typing import Optional
from parking_lot.enums import SpotType, TicketStatus, PaymentMethod, PaymentStatus, VehicleType
from parking_lot.vehicle import Vehicle, VehicleFactory
from parking_lot.spot import ParkingSpot
from parking_lot.floor import ParkingFloor
from parking_lot.ticket import ParkingTicket
from parking_lot.payment import Payment, PAYMENT_PROCESSORS
from parking_lot.report import Report
from database import load_parking_state, save_parking_state


class ParkingLot:
    """
    Singleton Parking Lot.
    Thread-safe vehicle entry, exit, and ticket management.
    Max: 5 floors | 1000 spots/floor | 5000 simultaneous vehicles.
    """

    _instance: Optional["ParkingLot"] = None
    _class_lock = threading.Lock()

    def __new__(cls):
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        # Lot info
        self.lot_id  = "ABC123"
        self.name    = "Vehicle PARKING"
        self.mobile  = "1234567890"
        self.address = "12/3, Address.."

        # State
        self.floors: dict[int, ParkingFloor] = {}
        self.tickets: dict[str, ParkingTicket] = {}         # ticket_id  → ticket
        self.vehicle_tickets: dict[str, str]   = {}         # vehicle_no → ticket_id
        self.payments: list[Payment]           = []
        self._op_lock = threading.Lock()

        self._setup_default_layout()
        self._load_state()

    def _load_state(self):
        state = load_parking_state()
        if not state["floors"]:
            return

        self.floors = {
            row["floor_number"]: ParkingFloor(row["floor_number"])
            for row in state["floors"]
        }
        spots_by_id = {}
        for row in state["spots"]:
            spot = ParkingSpot(
                row["spot_id"], row["spot_number"], SpotType(row["spot_type"])
            )
            if not row["is_available"]:
                spot.occupy()
            self.floors[row["floor_number"]].add_spot(spot)
            spots_by_id[spot.spot_id] = spot

        for row in state["tickets"]:
            vehicle = VehicleFactory.create(
                VehicleType(row["vehicle_type"]),
                row["vehicle_number"],
                row["color"] or "",
                row["owner_name"],
                row["owner_mobile"] or "",
            )
            ticket = ParkingTicket(
                vehicle, spots_by_id[row["spot_id"]], row["floor_number"]
            )
            ticket.ticket_id = row["ticket_id"]
            ticket.entry_time = datetime.fromisoformat(row["entry_time"])
            ticket.exit_time = (
                datetime.fromisoformat(row["exit_time"])
                if row["exit_time"] else None
            )
            ticket.status = TicketStatus(row["status"])
            self.tickets[ticket.ticket_id] = ticket
            if ticket.status != TicketStatus.PAID:
                self.vehicle_tickets[vehicle.vehicle_number] = ticket.ticket_id

        for row in state["payments"]:
            ticket = self.tickets.get(row["ticket_id"])
            if not ticket:
                continue
            payment = Payment(ticket, PaymentMethod(row["method"]))
            payment.payment_id = row["payment_id"]
            payment.status = PaymentStatus(row["status"])
            payment.amount = row["amount"]
            payment.paid_at = (
                datetime.fromisoformat(row["paid_at"])
                if row["paid_at"] else None
            )
            self.payments.append(payment)

    def save_state(self):
        spots = []
        for floor_number, floor in self.floors.items():
            for spot in floor.spots:
                spots.append({
                    "spot_id": spot.spot_id,
                    "floor_number": floor_number,
                    "spot_number": spot.spot_number,
                    "spot_type": spot.spot_type.value,
                    "is_available": spot.is_available,
                })

        tickets = []
        for ticket in self.tickets.values():
            tickets.append({
                "ticket_id": ticket.ticket_id,
                "vehicle_number": ticket.vehicle.vehicle_number,
                "vehicle_type": ticket.vehicle.vehicle_type.value,
                "color": ticket.vehicle.color,
                "owner_name": ticket.vehicle.owner_name,
                "owner_mobile": ticket.vehicle.owner_mobile,
                "spot_id": ticket.spot.spot_id,
                "floor_number": ticket.floor_number,
                "entry_time": ticket.entry_time.isoformat(),
                "exit_time": ticket.exit_time.isoformat() if ticket.exit_time else None,
                "status": ticket.status.value,
            })

        payments = [
            {
                "payment_id": payment.payment_id,
                "ticket_id": payment.ticket.ticket_id,
                "method": payment.method.value,
                "status": payment.status.value,
                "amount": payment.amount,
                "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
            }
            for payment in self.payments
        ]
        save_parking_state(sorted(self.floors), spots, tickets, payments)

    # ── Default Layout ────────────────────────────────────────────────────────

    def _setup_default_layout(self):
        """
        Ground Floor 1 — Truck + Bus spots (overflow Car/Bike slots included)
        Floor 2        — Car + Electric Car spots
        Floor 3        — Bike + Electric Bike spots
        """

        # Ground Floor 1
        f1 = ParkingFloor(1)
        for i in range(1, 11):
            f1.add_spot(ParkingSpot(f"SP-TRK-1-{i:02d}", f"G1-T{i:02d}",  SpotType.TRUCK))
        for i in range(1, 6):
            f1.add_spot(ParkingSpot(f"SP-BUS-1-{i:02d}", f"G1-B{i:02d}",  SpotType.BUS))
        for i in range(1, 6):
            f1.add_spot(ParkingSpot(f"SP-CAR-1-{i:02d}", f"G1-C{i:02d}",  SpotType.CAR))
        for i in range(1, 6):
            f1.add_spot(ParkingSpot(f"SP-BIK-1-{i:02d}", f"G1-BK{i:02d}", SpotType.BIKE))
        self.floors[1] = f1

        # Floor 2
        f2 = ParkingFloor(2)
        for i in range(1, 21):
            f2.add_spot(ParkingSpot(f"SP-CAR-2-{i:02d}", f"F2-C{i:02d}",  SpotType.CAR))
        for i in range(1, 11):
            f2.add_spot(ParkingSpot(f"SP-ECA-2-{i:02d}", f"F2-EC{i:02d}", SpotType.ELECTRIC_CAR))
        self.floors[2] = f2

        # Floor 3
        f3 = ParkingFloor(3)
        for i in range(1, 21):
            f3.add_spot(ParkingSpot(f"SP-BIK-3-{i:02d}", f"F3-BK{i:02d}", SpotType.BIKE))
        for i in range(1, 11):
            f3.add_spot(ParkingSpot(f"SP-EBK-3-{i:02d}", f"F3-EB{i:02d}", SpotType.ELECTRIC_BIKE))
        self.floors[3] = f3

    # ── Vehicle Entry ─────────────────────────────────────────────────────────

    def vehicle_entry(self, vehicle: Vehicle) -> Optional[ParkingTicket]:
        with self._op_lock:
            if vehicle.vehicle_number in self.vehicle_tickets:
                print(f"  ⚠ Vehicle {vehicle.vehicle_number} already has an active ticket.")
                return None

            if len(self.vehicle_tickets) >= 5000:
                print("  ⚠ Parking lot full (5000-vehicle limit reached).")
                return None

            spot, floor = self._find_spot(vehicle)
            if spot is None:
                print(f"  ⚠ No available spot for {vehicle.vehicle_type.value}.")
                return None

            if not spot.occupy():
                print("  ⚠ Spot was just taken. Please try again.")
                return None

            ticket = ParkingTicket(vehicle, spot, floor.floor_number)
            self.tickets[ticket.ticket_id]                 = ticket
            self.vehicle_tickets[vehicle.vehicle_number]   = ticket.ticket_id
            self.save_state()

            print(f"\n  ✅ Entry recorded for {vehicle.vehicle_number}")
            print(ticket)
            return ticket

    def _find_spot(self, vehicle: Vehicle):
        for floor in sorted(self.floors.values(), key=lambda f: f.floor_number):
            spot = floor.find_nearest_spot(vehicle.compatible_spots)
            if spot:
                return spot, floor
        return None, None

    # ── Vehicle Exit ──────────────────────────────────────────────────────────

    def vehicle_exit(self, vehicle_number: str,
                     method: PaymentMethod) -> Optional[Payment]:
        with self._op_lock:
            ticket_id = self.vehicle_tickets.get(vehicle_number.upper())
            if not ticket_id:
                print(f"  ⚠ No active ticket for {vehicle_number}.")
                return None

            ticket = self.tickets[ticket_id]
            if ticket.status != TicketStatus.ACTIVE:
                print(f"  ⚠ Ticket {ticket_id} status is already {ticket.status.value}.")
                return None

            payment = Payment(ticket, method)
            amount  = payment.calculate_amount()

            mins = ticket.duration_minutes()
            print(f"\n  🚗 Vehicle {vehicle_number} exiting.")
            print(f"  Duration : {int(mins // 60)}h {int(mins % 60)}m")
            print(f"  Amount   : ₹{amount:.2f} via {method.value}")

            processor = PAYMENT_PROCESSORS[method]
            success   = processor.pay(payment)

            if success:
                ticket.spot.free()
                del self.vehicle_tickets[vehicle_number.upper()]
                self.payments.append(payment)
                self.save_state()
                print(payment.receipt())
            else:
                payment.status = PaymentStatus.FAILED
                print("  ❌ Payment failed.")

            return payment

    # ── Lost Ticket ───────────────────────────────────────────────────────────

    def report_lost_ticket(self, vehicle_number: str):
        with self._op_lock:
            ticket_id = self.vehicle_tickets.get(vehicle_number.upper())
            if not ticket_id:
                print(f"  ⚠ No active ticket for {vehicle_number}.")
                return
            self.tickets[ticket_id].mark_lost()
            self.save_state()
            print(f"  ⚠ Ticket {ticket_id} marked as LOST.")

    # ── Display Boards ────────────────────────────────────────────────────────

    def show_all_displays(self):
        if not self.floors:
            print("  ℹ  No floors configured yet.")
            return

        print(f"\n{'═'*48}")
        print(f"  🅿  {self.name}  |  ID: {self.lot_id}")
        print(f"{'═'*48}")
        for floor in sorted(self.floors.values(), key=lambda f: f.floor_number):
            floor.show_display()

    def show_floor_display(self, floor_number: int):
        floor = self.floors.get(floor_number)
        if floor:
            floor.show_display()
        else:
            print(f"  ⚠ Floor {floor_number} not found.")

    # ── Ticket Lookup ─────────────────────────────────────────────────────────

    def get_ticket(self, ticket_id: str) -> Optional[ParkingTicket]:
        return self.tickets.get(ticket_id)

    def get_ticket_by_vehicle(self, vehicle_number: str) -> Optional[ParkingTicket]:
        tid = self.vehicle_tickets.get(vehicle_number.upper())
        return self.tickets.get(tid) if tid else None

    # ── Reports ───────────────────────────────────────────────────────────────

    def generate_report(self):
        Report(list(self.tickets.values()), self.payments).daily_report()
