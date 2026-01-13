import os
import json
import cv2
import numpy as np
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file
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
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'bmp'}
ALLOWED_CONFIG_EXTENSIONS = {'json', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def allowed_config(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_CONFIG_EXTENSIONS

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
    """Parking space ROI configuration page"""
    # Get current configuration if exists
    config = SystemConfig.query.filter_by(key='roi_config').first()
    frame_config = SystemConfig.query.filter_by(key='cctv_frame').first()
    
    roi_config = None
    frame_path = None
    
    if config:
        try:
            roi_config = json.loads(config.value)
        except:
            roi_config = None
    
    if frame_config:
        frame_path = frame_config.value
    
    return render_template('parking_spaces.html', 
                         roi_config=roi_config, 
                         frame_path=frame_path)

@app.route('/upload_roi_config', methods=['POST'])
def upload_roi_config():
    """Upload ROI configuration JSON file"""
    try:
        if 'config_file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['config_file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        if not allowed_config(file.filename):
            return jsonify({'success': False, 'message': 'Invalid file type. Only JSON files allowed'}), 400
        
        # Read and parse JSON
        content = file.read().decode('utf-8')
        roi_data = json.loads(content)
        
        # Validate JSON structure
        if not isinstance(roi_data, list):
            return jsonify({'success': False, 'message': 'Invalid JSON format. Expected array of ROI objects'}), 400
        
        for roi in roi_data:
            if 'type' not in roi or 'name' not in roi or 'points' not in roi:
                return jsonify({'success': False, 'message': 'Invalid ROI format. Each ROI must have type, name, and points'}), 400
        
        # Save to database
        config = SystemConfig.query.filter_by(key='roi_config').first()
        if config:
            config.value = json.dumps(roi_data)
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(key='roi_config', value=json.dumps(roi_data))
            db.session.add(config)
        
        # Create/update parking spaces from rectangles
        update_parking_spaces_from_config(roi_data)
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'ROI configuration uploaded successfully',
            'roi_count': len(roi_data)
        })
        
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'message': f'Invalid JSON format: {str(e)}'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error uploading configuration: {str(e)}'}), 500

@app.route('/upload_cctv_frame', methods=['POST'])
def upload_cctv_frame():
    """Upload CCTV frame image"""
    try:
        if 'frame_file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['frame_file']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        if not allowed_image(file.filename):
            return jsonify({'success': False, 'message': 'Invalid file type. Only JPG, PNG, BMP allowed'}), 400
        
        # Save frame image
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'cctv_frame_{timestamp}_{filename}'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Save path to database
        frame_config = SystemConfig.query.filter_by(key='cctv_frame').first()
        if frame_config:
            frame_config.value = filepath
            frame_config.updated_at = datetime.utcnow()
        else:
            frame_config = SystemConfig(key='cctv_frame', value=filepath)
            db.session.add(frame_config)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'CCTV frame uploaded successfully',
            'frame_path': filepath
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error uploading frame: {str(e)}'}), 500

@app.route('/generate_preview')
def generate_preview():
    """Generate preview image with ROI overlay"""
    try:
        # Get frame and config from database
        frame_config = SystemConfig.query.filter_by(key='cctv_frame').first()
        roi_config = SystemConfig.query.filter_by(key='roi_config').first()
        
        if not frame_config or not roi_config:
            return jsonify({'success': False, 'message': 'Frame or ROI configuration not found'}), 404
        
        # Load frame
        frame_path = frame_config.value
        if not os.path.exists(frame_path):
            return jsonify({'success': False, 'message': 'Frame file not found'}), 404
        
        frame = cv2.imread(frame_path)
        if frame is None:
            return jsonify({'success': False, 'message': 'Failed to load frame'}), 500
        
        # Parse ROI config
        roi_data = json.loads(roi_config.value)
        
        # Draw ROIs on frame
        preview_frame = draw_rois_on_frame(frame.copy(), roi_data)
        
        # Save preview image
        preview_filename = f'preview_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg'
        preview_path = os.path.join(app.config['UPLOAD_FOLDER'], preview_filename)
        cv2.imwrite(preview_path, preview_frame)
        
        return jsonify({
            'success': True,
            'message': 'Preview generated successfully',
            'preview_url': f'/get_preview/{preview_filename}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error generating preview: {str(e)}'}), 500

@app.route('/get_preview/<filename>')
def get_preview(filename):
    """Serve preview image"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            return send_file(filepath, mimetype='image/jpeg')
        else:
            return "File not found", 404
    except Exception as e:
        return str(e), 500

@app.route('/get_roi_config')
def get_roi_config():
    """Get current ROI configuration"""
    try:
        config = SystemConfig.query.filter_by(key='roi_config').first()
        if config:
            return jsonify({
                'success': True,
                'config': json.loads(config.value)
            })
        else:
            return jsonify({'success': False, 'message': 'No configuration found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

def draw_rois_on_frame(frame, roi_data):
    """Draw ROIs on frame using OpenCV"""
    # Color scheme
    colors = {
        'line': (0, 255, 255),      # Yellow for lines
        'rectangle': (0, 255, 0),   # Green for parking spaces
        'polyline': (255, 0, 255)   # Magenta for parking areas
    }
    
    for roi in roi_data:
        roi_type = roi['type']
        name = roi['name']
        points = roi['points']
        
        # Convert points to numpy array
        pts = np.array(points, dtype=np.int32)
        
        # Get color
        color = colors.get(roi_type, (255, 255, 255))
        
        if roi_type == 'line':
            # Draw line
            cv2.line(frame, tuple(pts[0]), tuple(pts[1]), color, 3)
            # Add label
            mid_point = ((pts[0][0] + pts[1][0]) // 2, (pts[0][1] + pts[1][1]) // 2)
            cv2.putText(frame, name, mid_point, cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
        elif roi_type == 'rectangle':
            # Draw rectangle
            cv2.rectangle(frame, tuple(pts[0]), tuple(pts[2]), color, 2)
            # Add label
            label_pos = (pts[0][0], pts[0][1] - 10)
            cv2.putText(frame, name, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            # Add semi-transparent fill
            overlay = frame.copy()
            cv2.rectangle(overlay, tuple(pts[0]), tuple(pts[2]), color, -1)
            cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
            
        elif roi_type == 'polyline':
            # Draw polyline
            cv2.polylines(frame, [pts], True, color, 2)
            # Add label at first point
            cv2.putText(frame, name, tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            # Add semi-transparent fill
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], color)
            cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
    
    return frame

def update_parking_spaces_from_config(roi_data):
    """Update ParkingSpace table from ROI configuration"""
    try:
        # Clear existing parking spaces
        ParkingSpace.query.delete()
        
        # Add new parking spaces from rectangles
        for roi in roi_data:
            if roi['type'] == 'rectangle':
                points = roi['points']
                # Get bounding box
                x1 = min(p[0] for p in points)
                y1 = min(p[1] for p in points)
                x2 = max(p[0] for p in points)
                y2 = max(p[1] for p in points)
                
                space = ParkingSpace(
                    name=roi['name'],
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    is_occupied=False
                )
                db.session.add(space)
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        raise e

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