"""
Parking space service - handles all business logic for parking space management
"""
import logging
from app import db
from models import ParkingSpace


class ParkingSpaceService:
    """Service class for parking space management operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_all_spaces(self):
        """
        Get all parking spaces
        
        Returns:
            list: List of all ParkingSpace objects
        """
        try:
            return ParkingSpace.query.all()
        except Exception as e:
            self.logger.error(f"Error fetching parking spaces: {e}")
            return []
    
    def get_space_by_id(self, space_id):
        """
        Get a parking space by ID
        
        Args:
            space_id (int): Parking space ID
            
        Returns:
            ParkingSpace: ParkingSpace object or None
        """
        try:
            return ParkingSpace.query.get(space_id)
        except Exception as e:
            self.logger.error(f"Error fetching parking space {space_id}: {e}")
            return None
    
    def create_space(self, name, x1, y1, x2, y2):
        """
        Create a new parking space
        
        Args:
            name (str): Space name
            x1 (int): Top-left X coordinate
            y1 (int): Top-left Y coordinate
            x2 (int): Bottom-right X coordinate
            y2 (int): Bottom-right Y coordinate
            
        Returns:
            tuple: (success: bool, message: str, space: ParkingSpace or None)
        """
        try:
            # Validate coordinates
            if x1 >= x2 or y1 >= y2:
                return False, "Invalid coordinates: x1 must be less than x2 and y1 must be less than y2", None
            
            # Check if space name already exists
            existing_space = ParkingSpace.query.filter_by(name=name).first()
            if existing_space:
                return False, f"Parking space with name '{name}' already exists", None
            
            # Create new space
            space = ParkingSpace(
                name=name,
                x1=int(x1),
                y1=int(y1),
                x2=int(x2),
                y2=int(y2)
            )
            
            db.session.add(space)
            db.session.commit()
            
            self.logger.info(f"Created parking space: {name}")
            return True, "Parking space created successfully", space
            
        except ValueError as e:
            db.session.rollback()
            self.logger.error(f"Value error creating parking space: {e}")
            return False, "Invalid coordinate values", None
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error creating parking space: {e}")
            return False, str(e), None
    
    def update_space(self, space_id, name=None, x1=None, y1=None, x2=None, y2=None):
        """
        Update an existing parking space
        
        Args:
            space_id (int): Parking space ID
            name (str, optional): New space name
            x1, y1, x2, y2 (int, optional): New coordinates
            
        Returns:
            tuple: (success: bool, message: str, space: ParkingSpace or None)
        """
        try:
            space = ParkingSpace.query.get(space_id)
            if not space:
                return False, f"Parking space {space_id} not found", None
            
            # Update fields if provided
            if name is not None:
                # Check if new name conflicts with another space
                existing = ParkingSpace.query.filter(
                    ParkingSpace.name == name,
                    ParkingSpace.id != space_id
                ).first()
                if existing:
                    return False, f"Space name '{name}' already exists", None
                space.name = name
            
            if all(v is not None for v in [x1, y1, x2, y2]):
                if x1 >= x2 or y1 >= y2:
                    return False, "Invalid coordinates", None
                space.x1 = int(x1)
                space.y1 = int(y1)
                space.x2 = int(x2)
                space.y2 = int(y2)
            
            db.session.commit()
            
            self.logger.info(f"Updated parking space: {space.name}")
            return True, "Parking space updated successfully", space
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error updating parking space: {e}")
            return False, str(e), None
    
    def delete_space(self, space_id):
        """
        Delete a parking space
        
        Args:
            space_id (int): Parking space ID
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            space = ParkingSpace.query.get(space_id)
            if not space:
                return False, f"Parking space {space_id} not found"
            
            space_name = space.name
            
            # Check if space is currently occupied
            if space.is_occupied:
                self.logger.warning(f"Attempting to delete occupied space: {space_name}")
                # You might want to prevent deletion or handle this differently
            
            db.session.delete(space)
            db.session.commit()
            
            self.logger.info(f"Deleted parking space: {space_name}")
            return True, f"Parking space '{space_name}' deleted successfully"
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error deleting parking space: {e}")
            return False, str(e)
    
    def get_available_spaces(self):
        """
        Get all available (unoccupied) parking spaces
        
        Returns:
            list: List of available ParkingSpace objects
        """
        try:
            return ParkingSpace.query.filter_by(is_occupied=False).all()
        except Exception as e:
            self.logger.error(f"Error fetching available spaces: {e}")
            return []
    
    def get_occupied_spaces(self):
        """
        Get all occupied parking spaces
        
        Returns:
            list: List of occupied ParkingSpace objects
        """
        try:
            return ParkingSpace.query.filter_by(is_occupied=True).all()
        except Exception as e:
            self.logger.error(f"Error fetching occupied spaces: {e}")
            return []
    
    def get_space_utilization(self):
        """
        Calculate parking space utilization statistics
        
        Returns:
            dict: Dictionary containing utilization statistics
        """
        try:
            total = ParkingSpace.query.count()
            occupied = ParkingSpace.query.filter_by(is_occupied=True).count()
            available = total - occupied
            
            utilization_rate = (occupied / total * 100) if total > 0 else 0
            
            return {
                'total': total,
                'occupied': occupied,
                'available': available,
                'utilization_rate': round(utilization_rate, 2)
            }
        except Exception as e:
            self.logger.error(f"Error calculating space utilization: {e}")
            return {
                'total': 0,
                'occupied': 0,
                'available': 0,
                'utilization_rate': 0
            }