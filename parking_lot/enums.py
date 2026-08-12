from enum import Enum


class VehicleType(Enum):
    BIKE          = "Bike"
    ELECTRIC_BIKE = "Electric Bike"
    CAR           = "Car"
    ELECTRIC_CAR  = "Electric Car"
    TRUCK         = "Truck"
    BUS           = "Bus"


class SpotType(Enum):
    BIKE          = "Bike Spot"
    ELECTRIC_BIKE = "Electric Bike Spot"
    CAR           = "Car Spot"
    ELECTRIC_CAR  = "Electric Car Spot"
    TRUCK         = "Truck Spot"
    BUS           = "Bus Spot"


class TicketStatus(Enum):
    ACTIVE = "ACTIVE"
    PAID   = "PAID"
    LOST   = "LOST"


class PaymentMethod(Enum):
    CASH = "Cash"
    CARD = "Card"
    UPI  = "UPI"


class PaymentStatus(Enum):
    PENDING   = "Pending"
    COMPLETED = "Completed"
    FAILED    = "Failed"
    REFUNDED  = "Refunded"


HOURLY_RATES: dict[VehicleType, float] = {
    VehicleType.BIKE:          20.0,
    VehicleType.ELECTRIC_BIKE: 30.0,
    VehicleType.CAR:           40.0,
    VehicleType.ELECTRIC_CAR:  50.0,
    VehicleType.BUS:          100.0,
    VehicleType.TRUCK:        150.0,
}
