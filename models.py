from datetime import datetime
from app import db  # ✅ Import db from app.py instead of creating a new one
from sqlalchemy import func

class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    
    id = db.Column(db.Integer, primary_key=True)
    license_plate = db.Column(db.String(20), unique=True, nullable=False)
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    total_visits = db.Column(db.Integer, default=1)
    
    # Relationships
    parking_sessions = db.relationship('ParkingSession', backref='vehicle', lazy=True)
    
    def __repr__(self):
        return f'<Vehicle {self.license_plate}>'

class ParkingSpace(db.Model):
    __tablename__ = 'parking_spaces'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    x1 = db.Column(db.Integer, nullable=False)
    y1 = db.Column(db.Integer, nullable=False)
    x2 = db.Column(db.Integer, nullable=False)
    y2 = db.Column(db.Integer, nullable=False)
    is_occupied = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    parking_sessions = db.relationship('ParkingSession', backref='parking_space', lazy=True)
    
    def __repr__(self):
        return f'<ParkingSpace {self.name}>'

class ParkingSession(db.Model):
    __tablename__ = 'parking_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicles.id'), nullable=False)
    parking_space_id = db.Column(db.Integer, db.ForeignKey('parking_spaces.id'), nullable=True)
    entry_time = db.Column(db.DateTime, default=datetime.utcnow)
    exit_time = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    toll_amount = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    
    def calculate_toll(self):
        """Calculate toll based on parking duration"""
        if self.exit_time and self.entry_time:
            duration = self.exit_time - self.entry_time
            self.duration_minutes = int(duration.total_seconds() / 60)
            
            if self.duration_minutes <= 60:
                self.toll_amount = 2.0
            else:
                additional_hours = (self.duration_minutes - 60) // 60 + (1 if (self.duration_minutes - 60) % 60 > 0 else 0)
                self.toll_amount = 2.0 + (additional_hours * 1.0)
        
        return self.toll_amount
    
    def __repr__(self):
        return f'<ParkingSession {self.id}>'

class DetectionLog(db.Model):
    __tablename__ = 'detection_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    detection_type = db.Column(db.String(20), nullable=False)
    license_plate = db.Column(db.String(20), nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    vehicle_count = db.Column(db.Integer, default=0)
    frame_path = db.Column(db.String(255), nullable=True)
    
    def __repr__(self):
        return f'<DetectionLog {self.id}: {self.detection_type}>'

class SystemConfig(db.Model):
    __tablename__ = 'system_config'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemConfig {self.key}: {self.value}>'