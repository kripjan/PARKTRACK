from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Model
class ParkingRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.Integer, nullable=False)
    vehicle_type = db.Column(db.String(50), nullable=False)
    license_plate = db.Column(db.String(20), nullable=True)
    entry_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    exit_time = db.Column(db.DateTime, nullable=True)
    total_hours = db.Column(db.Float, nullable=True)
    parking_fee = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='parked')  # 'parked' or 'exited'

    def calculate_fee(self, hourly_rate):
        if self.exit_time and self.entry_time:
            duration = (self.exit_time - self.entry_time).total_seconds() / 3600
            self.total_hours = round(duration, 2)
            self.parking_fee = round(duration * hourly_rate, 2)
        return self.parking_fee

# Create tables
with app.app_context():
    db.create_all()

# Hourly rates for different vehicle types
HOURLY_RATES = {
    'Car': 50.0,
    'Motorcycle': 20.0,
    'Bus': 100.0,
    'Truck': 80.0,
    'Person': 0.0
}

# API Routes
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/vehicle/entry', methods=['POST'])
def vehicle_entry():
    """Record vehicle entry"""
    data = request.json
    
    new_record = ParkingRecord(
        track_id=data['track_id'],
        vehicle_type=data['vehicle_type'],
        license_plate=data.get('license_plate', 'Unknown'),
        entry_time=datetime.utcnow(),
        status='parked'
    )
    
    db.session.add(new_record)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'record_id': new_record.id,
        'message': f"{data['vehicle_type']} (Track ID: {data['track_id']}) entered"
    })

@app.route('/api/vehicle/exit', methods=['POST'])
def vehicle_exit():
    """Record vehicle exit and calculate fee"""
    data = request.json
    track_id = data['track_id']
    
    # Find the most recent parked record for this track_id
    record = ParkingRecord.query.filter_by(
        track_id=track_id, 
        status='parked'
    ).order_by(ParkingRecord.entry_time.desc()).first()
    
    if not record:
        return jsonify({'success': False, 'message': 'No entry record found'}), 404
    
    record.exit_time = datetime.utcnow()
    record.status = 'exited'
    
    # Calculate fee
    hourly_rate = HOURLY_RATES.get(record.vehicle_type, 50.0)
    fee = record.calculate_fee(hourly_rate)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'record_id': record.id,
        'track_id': track_id,
        'vehicle_type': record.vehicle_type,
        'license_plate': record.license_plate,
        'entry_time': record.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
        'exit_time': record.exit_time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_hours': record.total_hours,
        'parking_fee': record.parking_fee,
        'message': f'Total fee: Rs. {fee}'
    })

@app.route('/api/vehicles/current', methods=['GET'])
def get_current_vehicles():
    """Get all currently parked vehicles"""
    vehicles = ParkingRecord.query.filter_by(status='parked').all()
    
    return jsonify({
        'count': len(vehicles),
        'vehicles': [{
            'id': v.id,
            'track_id': v.track_id,
            'vehicle_type': v.vehicle_type,
            'license_plate': v.license_plate,
            'entry_time': v.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_hours': round((datetime.utcnow() - v.entry_time).total_seconds() / 3600, 2)
        } for v in vehicles]
    })

@app.route('/api/vehicles/history', methods=['GET'])
def get_vehicle_history():
    """Get all vehicle history"""
    vehicles = ParkingRecord.query.order_by(ParkingRecord.entry_time.desc()).all()
    
    return jsonify({
        'count': len(vehicles),
        'vehicles': [{
            'id': v.id,
            'track_id': v.track_id,
            'vehicle_type': v.vehicle_type,
            'license_plate': v.license_plate,
            'entry_time': v.entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': v.exit_time.strftime('%Y-%m-%d %H:%M:%S') if v.exit_time else None,
            'total_hours': v.total_hours,
            'parking_fee': v.parking_fee,
            'status': v.status
        } for v in vehicles]
    })

@app.route('/api/rates', methods=['GET'])
def get_rates():
    """Get current hourly rates"""
    return jsonify(HOURLY_RATES)

@app.route('/api/rates', methods=['POST'])
def update_rates():
    """Update hourly rates"""
    data = request.json
    for vehicle_type, rate in data.items():
        if vehicle_type in HOURLY_RATES:
            HOURLY_RATES[vehicle_type] = float(rate)
    
    return jsonify({'success': True, 'rates': HOURLY_RATES})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get parking statistics"""
    total_records = ParkingRecord.query.count()
    parked = ParkingRecord.query.filter_by(status='parked').count()
    exited = ParkingRecord.query.filter_by(status='exited').count()
    total_revenue = db.session.query(db.func.sum(ParkingRecord.parking_fee)).scalar() or 0
    
    return jsonify({
        'total_vehicles': total_records,
        'currently_parked': parked,
        'exited': exited,
        'total_revenue': round(total_revenue, 2)
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)