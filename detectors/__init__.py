"""
Detectors package - Contains all detection logic
"""
from .parking_detector import ParkingDetector
from .license_plate_detector import LicensePlateDetector
from .image_plate_detector import ImagePlateDetector

__all__ = [
    'ParkingDetector',
    'LicensePlateDetector',
    'ImagePlateDetector'
]
