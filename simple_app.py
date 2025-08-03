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

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Import db from models to avoid circular imports
from models import db

# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://localhost/smart_parking")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max file size

# Ensure upload directory exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# initialize extensions
db.init_app(app)

with app.app_context():
    # Create all tables
    db.create_all()

# Import components
from video_processor import VideoProcessor
from parking_manager import ParkingManager

# Initialize components
video_processor = VideoProcessor()
parking_manager = ParkingManager()

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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