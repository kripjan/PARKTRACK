#!/usr/bin/env python3
"""
Simplified Flask app for the Smart Parking System without SocketIO complexity
This version focuses on core functionality first
"""

import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from flask_socketio import SocketIO
import math

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///parking.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max file size

# Ensure upload directory exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Import db from models to avoid circular imports
from models import db, VehicleRecord

# initialize extensions
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")

RATE_PER_HOUR = 20  # Rs per hour

with app.app_context():
    # Create all tables
    db.create_all()


def calculate_amount(entry_time, exit_time):
    hours = (exit_time - entry_time).total_seconds() / 3600
    hours = max(1, math.ceil(hours))
    return f"{hours} hrs", hours * RATE_PER_HOUR


# Import components
from video_processor import VideoProcessor
from parking_manager import ParkingManager

# Initialize components
video_processor = VideoProcessor()
parking_manager = ParkingManager()

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# @app.route("/")
# def vehicle_records():
#     records = VehicleRecord.query.order_by(VehicleRecord.entry_time.asc()).all()
#     return render_template("vehicle_entry_exit_records.html", records=records)


# Routes
@app.route('/')
def dashboard():
    """Main dashboard with parking status"""
    from models import Vehicle, ParkingSpace, ParkingSession, DetectionLog
    
    # Get current parking statistics
    total_spaces = ParkingSpace.query.count()
    occupied_spaces = ParkingSpace.query.filter_by(is_occupied=True).count()
    available_spaces = total_spaces - occupied_spaces
    
    # Get active parking sessions
    active_sessions = ParkingSession.query.filter_by(is_active=True).all()
    
    # Get recent detections
    recent_detections = DetectionLog.query.order_by(desc(DetectionLog.timestamp)).limit(10).all()
    
    # Calculate today's revenue
    today = datetime.utcnow().date()
    today_revenue = db.session.query(func.sum(ParkingSession.toll_amount)).filter(
        func.date(ParkingSession.exit_time) == today,
        ParkingSession.is_active == False
    ).scalar() or 0.0
    
    return render_template('dashboard.html',
                         total_spaces=total_spaces,
                         occupied_spaces=occupied_spaces,
                         available_spaces=available_spaces,
                         active_sessions=active_sessions,
                         recent_detections=recent_detections,
                         today_revenue=today_revenue)



@app.route('/video_upload')
def video_upload():
    """Video upload and processing page"""
    return render_template('video_upload.html')



@app.route('/upload_video', methods=['POST'])
def upload_video():
    """Handle video file upload and start processing"""
    if 'video' not in request.files:
        flash('No video file selected', 'error')
        return redirect(request.url)
    
    file = request.files['video']
    if file.filename == '':
        flash('No video file selected', 'error')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Start video processing in background
        video_processor.process_video_file(filepath)
        
        flash(f'Video {filename} uploaded and processing started!', 'success')
        return redirect(url_for('video_upload'))
    else:
        flash('Invalid file type. Please upload MP4, AVI, MOV, or MKV files.', 'error')
        return redirect(request.url)
    
    

@app.route('/vehicle_entry_exit_records')
def vehicle_entry_exit_records():
    """Parking space management page"""
    records = VehicleRecord.query.order_by(VehicleRecord.entry_time.asc()).all()
    return render_template("vehicle_entry_exit_records.html", records=records)
    

# VEHICLE ENTRY
@app.route("/vehicle/entry", methods=["POST"])
def vehicle_entry():
    data = request.json
    vehicle_no = data.get("vehicle_no")

    vehicle = VehicleRecord(
        vehicle_no=vehicle_no,
        entry_time=datetime.utcnow()
    )
    db.session.add(vehicle)
    db.session.commit()

    socketio.emit("new_vehicle_entry", {
        "vehicle_no": vehicle.vehicle_no,
        "entry_time": vehicle.entry_time.strftime("%Y-%m-%d %H:%M"),
        "amount": 0
    })

    return jsonify({"status": "success"})


# VEHICLE EXIT
@app.route("/vehicle/exit", methods=["POST"])
def vehicle_exit():
    data = request.json
    vehicle_no = data.get("vehicle_no")

    vehicle = VehicleRecord.query.filter_by(
        vehicle_no=vehicle_no,
        exit_time=None
    ).first()

    if not vehicle:
        return jsonify({"error": "Vehicle not found"}), 404

    vehicle.exit_time = datetime.utcnow()
    vehicle.duration, vehicle.amount = calculate_amount(
        vehicle.entry_time,
        vehicle.exit_time
    )

    db.session.commit()

    socketio.emit("vehicle_exit", {
        "vehicle_no": vehicle.vehicle_no,
        "exit_time": vehicle.exit_time.strftime("%Y-%m-%d %H:%M"),
        "duration": vehicle.duration,
        "amount": vehicle.amount
    })

    return jsonify({"status": "exited"})


@app.route('/parking_spaces')
def parking_spaces():
    """Parking space management page"""
    from models import ParkingSpace
    spaces = ParkingSpace.query.all()
    return render_template('parking_spaces.html', spaces=spaces)

@app.route('/reports')
def reports():
    """Reports and analytics page"""
    from models import Vehicle, ParkingSpace, ParkingSession, DetectionLog
    
    # Get some basic statistics for the reports
    total_vehicles = Vehicle.query.count()
    total_sessions = ParkingSession.query.count()
    total_revenue = db.session.query(func.sum(ParkingSession.toll_amount)).filter(
        ParkingSession.is_active == False
    ).scalar() or 0.0
    
    # Get recent sessions for the table
    recent_sessions = ParkingSession.query.order_by(desc(ParkingSession.entry_time)).limit(20).all()
    
    return render_template('reports.html',
                         total_vehicles=total_vehicles,
                         total_sessions=total_sessions,
                         total_revenue=total_revenue,
                         recent_sessions=recent_sessions)
    
    
    

@app.route('/api/start_live_feed', methods=['POST'])
def start_live_feed():
    """Start live camera feed processing"""
    camera_index = request.json.get('camera_index', 0)
    
    if video_processor.is_processing:
        return jsonify({'success': False, 'message': 'Video processing already in progress'})
    
    video_processor.start_live_feed(camera_index)
    return jsonify({'success': True, 'message': 'Live feed started'})




@app.route('/api/stop_processing', methods=['POST'])
def stop_processing():
    """Stop current video processing"""
    video_processor.stop_processing()
    return jsonify({'success': True, 'message': 'Processing stopped'})



@app.route('/stop_live_feed', methods=['POST'])
def stop_live_feed():
    """Stop live camera feed processing"""
    video_processor.stop_processing()
    flash('Live feed stopped', 'info')
    return redirect(url_for('dashboard'))




@app.route('/start_live_feed_ui', methods=['POST'])
def start_live_feed_ui():
    """Start live camera feed processing from UI"""
    if video_processor.is_processing:
        flash('Video processing already in progress', 'warning')
    else:
        video_processor.start_live_feed(0)  # Use camera index 0
        flash('Live feed started', 'success')
    return redirect(url_for('dashboard'))




@app.route('/api/parking_status')
def parking_status():
    """Get current parking status as JSON"""
    from models import ParkingSpace, ParkingSession
    
    total_spaces = ParkingSpace.query.count()
    occupied_spaces = ParkingSpace.query.filter_by(is_occupied=True).count()
    available_spaces = total_spaces - occupied_spaces
    active_sessions = ParkingSession.query.filter_by(is_active=True).count()
    
    return jsonify({
        'total_spaces': total_spaces,
        'occupied_spaces': occupied_spaces,
        'available_spaces': available_spaces,
        'active_sessions': active_sessions
    })




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)