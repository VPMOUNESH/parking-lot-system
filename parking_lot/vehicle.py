"""
vehicle.py — Vehicle abstract base class, concrete vehicle types, and VehicleFactory
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from parking_lot.enums import VehicleType, SpotType


class Vehicle(ABC):
    def __init__(self, vehicle_number: str, color: str,
                 owner_name: str, owner_mobile: str):
        self.vehicle_number = vehicle_number.upper()
        self.color          = color
        self.owner_name     = owner_name
        self.owner_mobile   = owner_mobile

    @property
    @abstractmethod
    def vehicle_type(self) -> VehicleType:
        pass

    @property
    @abstractmethod
    def compatible_spots(self) -> list[SpotType]:
        """Ordered list of spot types this vehicle can park in (preference order)."""
        pass

    def __str__(self):
        return (f"[{self.vehicle_type.value}] {self.vehicle_number} | "
                f"Color: {self.color} | Owner: {self.owner_name} | "
                f"Mobile: {self.owner_mobile}")


# ── Concrete Vehicle Types ────────────────────────────────────────────────────

class Bike(Vehicle):
    @property
    def vehicle_type(self):    return VehicleType.BIKE
    @property
    def compatible_spots(self): return [SpotType.BIKE]


class ElectricBike(Vehicle):
    @property
    def vehicle_type(self):    return VehicleType.ELECTRIC_BIKE
    @property
    def compatible_spots(self): return [SpotType.ELECTRIC_BIKE, SpotType.BIKE]


class Car(Vehicle):
    @property
    def vehicle_type(self):    return VehicleType.CAR
    @property
    def compatible_spots(self): return [SpotType.CAR]


class ElectricCar(Vehicle):
    @property
    def vehicle_type(self):    return VehicleType.ELECTRIC_CAR
    @property
    def compatible_spots(self): return [SpotType.ELECTRIC_CAR, SpotType.CAR]


class Truck(Vehicle):
    @property
    def vehicle_type(self):    return VehicleType.TRUCK
    @property
    def compatible_spots(self): return [SpotType.TRUCK, SpotType.BUS]


class Bus(Vehicle):
    @property
    def vehicle_type(self):    return VehicleType.BUS
    @property
    def compatible_spots(self): return [SpotType.BUS, SpotType.TRUCK]


# ── Factory ───────────────────────────────────────────────────────────────────

class VehicleFactory:
    """Creates Vehicle instances. Register new types without modifying core code."""

    _registry: dict[VehicleType, type[Vehicle]] = {
        VehicleType.BIKE:          Bike,
        VehicleType.ELECTRIC_BIKE: ElectricBike,
        VehicleType.CAR:           Car,
        VehicleType.ELECTRIC_CAR:  ElectricCar,
        VehicleType.TRUCK:         Truck,
        VehicleType.BUS:           Bus,
    }

    @classmethod
    def create(cls, v_type: VehicleType, number: str,
               color: str, owner: str, mobile: str) -> Vehicle:
        klass = cls._registry.get(v_type)
        if klass is None:
            raise ValueError(f"Unsupported vehicle type: {v_type}")
        return klass(number, color, owner, mobile)

    @classmethod
    def register(cls, v_type: VehicleType, klass: type[Vehicle]):
        """Extend with a new vehicle type at runtime (Open/Closed Principle)."""
        cls._registry[v_type] = klass
