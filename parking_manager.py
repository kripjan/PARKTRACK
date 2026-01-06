import logging
from datetime import datetime
from models import db
from models import Vehicle, ParkingSession, ParkingSpace

class ParkingManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.broadcast_function = None
    
    def set_broadcast_function(self, broadcast_function):
        """Set broadcast function for real-time updates"""
        self.broadcast_function = broadcast_function
    
    def handle_vehicle_detection(self, license_plate):
        """
        Handle vehicle detection and manage parking sessions
        
        Args:
            license_plate (str): Detected license plate
        """
        try:
            with db.session.begin():
                # Find or create vehicle record
                vehicle = Vehicle.query.filter_by(license_plate=license_plate).first()
                
                if not vehicle:
                    # New vehicle
                    vehicle = Vehicle(license_plate=license_plate)
                    db.session.add(vehicle)
                    db.session.flush()  # To get the ID
                    self.logger.info(f"New vehicle registered: {license_plate}")
                else:
                    # Update existing vehicle
                    vehicle.last_seen = datetime.utcnow()
                    vehicle.total_visits += 1
                    self.logger.info(f"Existing vehicle detected: {license_plate}")
                
                # Check if vehicle has an active parking session
                active_session = ParkingSession.query.filter_by(
                    vehicle_id=vehicle.id,
                    is_active=True
                ).first()
                
                if active_session:
                    # Vehicle is exiting
                    self._handle_vehicle_exit(active_session)
                else:
                    # Vehicle is entering
                    self._handle_vehicle_entry(vehicle)
                
                db.session.commit()
                
        except Exception as e:
            self.logger.error(f"Error handling vehicle detection: {e}")
            db.session.rollback()
    
    def _handle_vehicle_entry(self, vehicle):
        """Handle vehicle entry to parking area"""
        try:
            # Find an available parking space
            available_space = ParkingSpace.query.filter_by(is_occupied=False).first()
            
            # Create new parking session
            session = ParkingSession(
                vehicle_id=vehicle.id,
                parking_space_id=available_space.id if available_space else None,
                entry_time=datetime.utcnow(),
                is_active=True
            )
            db.session.add(session)
            
            # Mark parking space as occupied if assigned
            if available_space:
                available_space.is_occupied = True
                self.logger.info(f"Vehicle {vehicle.license_plate} assigned to space {available_space.name}")
            else:
                self.logger.warning(f"No available parking space for vehicle {vehicle.license_plate}")
            
            # Broadcast update
            if self.broadcast_function:
                self.broadcast_function({
                    'type': 'entry',
                    'license_plate': vehicle.license_plate,
                    'space_name': available_space.name if available_space else 'No space assigned',
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            self.logger.info(f"Vehicle entry recorded: {vehicle.license_plate}")
            
        except Exception as e:
            self.logger.error(f"Error handling vehicle entry: {e}")
            raise
    
    def _handle_vehicle_exit(self, session):
        """Handle vehicle exit from parking area"""
        try:
            # Update session with exit time
            session.exit_time = datetime.utcnow()
            session.is_active = False
            
            # Calculate toll
            toll_amount = session.calculate_toll()
            
            # Free up parking space
            if session.parking_space:
                session.parking_space.is_occupied = False
                space_name = session.parking_space.name
            else:
                space_name = 'Unknown'
            
            # Broadcast update
            if self.broadcast_function:
                self.broadcast_function({
                    'type': 'exit',
                    'license_plate': session.vehicle.license_plate,
                    'space_name': space_name,
                    'duration_minutes': session.duration_minutes,
                    'toll_amount': toll_amount,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            self.logger.info(f"Vehicle exit recorded: {session.vehicle.license_plate}, "
                           f"Duration: {session.duration_minutes} min, Toll: ${toll_amount:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error handling vehicle exit: {e}")
            raise
    
    def get_parking_statistics(self):
        """Get current parking statistics"""
        try:
            total_spaces = ParkingSpace.query.count()
            occupied_spaces = ParkingSpace.query.filter_by(is_occupied=True).count()
            available_spaces = total_spaces - occupied_spaces
            active_sessions = ParkingSession.query.filter_by(is_active=True).count()
            
            return {
                'total_spaces': total_spaces,
                'occupied_spaces': occupied_spaces,
                'available_spaces': available_spaces,
                'active_sessions': active_sessions
            }
            
        except Exception as e:
            self.logger.error(f"Error getting parking statistics: {e}")
            return {
                'total_spaces': 0,
                'occupied_spaces': 0,
                'available_spaces': 0,
                'active_sessions': 0
            }
    
    def assign_parking_space(self, vehicle_id, space_id):
        """Manually assign a parking space to a vehicle"""
        try:
            with db.session.begin():
                space = ParkingSpace.query.get(space_id)
                if not space:
                    raise ValueError(f"Parking space {space_id} not found")
                
                if space.is_occupied:
                    raise ValueError(f"Parking space {space.name} is already occupied")
                
                # Find active session for vehicle
                session = ParkingSession.query.filter_by(
                    vehicle_id=vehicle_id,
                    is_active=True
                ).first()
                
                if not session:
                    raise ValueError(f"No active parking session found for vehicle")
                
                # Update session and space
                session.parking_space_id = space_id
                space.is_occupied = True
                
                db.session.commit()
                
                self.logger.info(f"Manually assigned space {space.name} to vehicle {session.vehicle.license_plate}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error assigning parking space: {e}")
            db.session.rollback()
            raise
    
    def release_parking_space(self, space_id):
        """Manually release a parking space"""
        try:
            with db.session.begin():
                space = ParkingSpace.query.get(space_id)
                if not space:
                    raise ValueError(f"Parking space {space_id} not found")
                
                # Find active session in this space
                session = ParkingSession.query.filter_by(
                    parking_space_id=space_id,
                    is_active=True
                ).first()
                
                if session:
                    # End the parking session
                    session.exit_time = datetime.utcnow()
                    session.is_active = False
                    session.calculate_toll()
                
                # Free the space
                space.is_occupied = False
                
                db.session.commit()
                
                self.logger.info(f"Manually released parking space {space.name}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error releasing parking space: {e}")
            db.session.rollback()
            raise
