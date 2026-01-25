"""
Detectors package - Contains all detection logic
"""
from .parking_detector import ParkingDetector
from .license_plate_detector import LicensePlateDetector

__all__ = [
    'ParkingDetector',
    'LicensePlateDetector'
]
