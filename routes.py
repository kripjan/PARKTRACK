import os
import json
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_socketio import emit
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc
from app import app, db, socketio
from models import Vehicle, ParkingSpace, ParkingSession, DetectionLog, SystemConfig
from video_processor import VideoProcessor
from parking_manager import ParkingManager

# Initialize components
video_processor = VideoProcessor()
parking_manager = ParkingManager()

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def dashboard():
    """Main dashboard with real-time parking status"""
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
        
        flash('Video uploaded successfully and processing started', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Invalid file type. Please upload MP4, AVI, MOV, or MKV files.', 'error')
        return redirect(request.url)

@app.route('/parking_spaces')
def parking_spaces():
    """Parking space management page"""
    spaces = ParkingSpace.query.all()
    return render_template('parking_spaces.html', spaces=spaces)

@app.route('/add_parking_space', methods=['POST'])
def add_parking_space():
    """Add a new parking space"""
    data = request.get_json()
    
    try:
        space = ParkingSpace(
            name=data['name'],
            x1=int(data['x1']),
            y1=int(data['y1']),
            x2=int(data['x2']),
            y2=int(data['y2'])
        )
        db.session.add(space)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Parking space added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/delete_parking_space/<int:space_id>', methods=['DELETE'])
def delete_parking_space(space_id):
    """Delete a parking space"""
    try:
        space = ParkingSpace.query.get_or_404(space_id)
        db.session.delete(space)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Parking space deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/reports')
def reports():
    """Reports and analytics page"""
    # Get data for the last 7 days
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    
    # Daily revenue data
    daily_revenue = db.session.query(
        func.date(ParkingSession.exit_time).label('date'),
        func.sum(ParkingSession.toll_amount).label('revenue')
    ).filter(
        ParkingSession.exit_time.between(start_date, end_date),
        ParkingSession.is_active == False
    ).group_by(func.date(ParkingSession.exit_time)).all()
    
    # Hourly occupancy data for today
    today = datetime.utcnow().date()
    hourly_occupancy = db.session.query(
        func.extract('hour', DetectionLog.timestamp).label('hour'),
        func.count(DetectionLog.id).label('count')
    ).filter(
        func.date(DetectionLog.timestamp) == today,
        DetectionLog.detection_type == 'entry'
    ).group_by(func.extract('hour', DetectionLog.timestamp)).all()
    
    # Top vehicles (most frequent visitors)
    top_vehicles = db.session.query(
        Vehicle.license_plate,
        Vehicle.total_visits,
        func.sum(ParkingSession.toll_amount).label('total_paid')
    ).join(ParkingSession).filter(
        ParkingSession.is_active == False
    ).group_by(Vehicle.id).order_by(desc(Vehicle.total_visits)).limit(10).all()
    
    return render_template('reports.html',
                         daily_revenue=daily_revenue,
                         hourly_occupancy=hourly_occupancy,
                         top_vehicles=top_vehicles)

@app.route('/start_live_feed', methods=['POST'])
def start_live_feed():
    """Start processing live video feed"""
    try:
        camera_index = request.form.get('camera_index', 0, type=int)
        video_processor.start_live_processing(camera_index)
        flash('Live feed processing started', 'success')
    except Exception as e:
        flash(f'Error starting live feed: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/stop_live_feed', methods=['POST'])
def stop_live_feed():
    """Stop processing live video feed"""
    try:
        video_processor.stop_live_processing()
        flash('Live feed processing stopped', 'success')
    except Exception as e:
        flash(f'Error stopping live feed: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

# WebSocket events for real-time updates
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {'msg': 'Connected to Smart Parking System'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

def broadcast_parking_update(data):
    """Broadcast parking space updates to all connected clients"""
    socketio.emit('parking_update', data)

def broadcast_detection(detection_data):
    """Broadcast new vehicle detection to all connected clients"""
    socketio.emit('new_detection', detection_data)

# Make these functions available to other modules
video_processor.set_broadcast_functions(broadcast_parking_update, broadcast_detection)
parking_manager.set_broadcast_function(broadcast_parking_update)
