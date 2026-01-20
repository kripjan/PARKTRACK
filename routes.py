"""
Routes module - Dashboard with video upload, separate Parking Spaces page, Video Processing for plate detection
"""
import os
import json
import glob
from flask import render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_socketio import emit
from werkzeug.utils import secure_filename
from app import app, socketio
from services import DashboardService, VideoService, ReportService, ParkingSpaceService
from parking_manager import ParkingManager

# Initialize services
dashboard_service = DashboardService()
video_service = VideoService()
report_service = ReportService()
parking_space_service = ParkingSpaceService(app.config['UPLOAD_FOLDER'])
parking_manager = ParkingManager()


# ============================================================================
# DASHBOARD ROUTES (with Video Upload for vehicle detection)
# ============================================================================

@app.route('/')
def dashboard():
    """Main dashboard with real-time parking status and video upload"""
    data = dashboard_service.get_dashboard_data()
    return render_template('dashboard.html', **data)


@app.route('/upload_video', methods=['POST'])
def upload_video():
    """Handle video file upload from dashboard and start parking detection"""
    if 'video' not in request.files:
        return jsonify({'success': False, 'message': 'No video file selected'}), 400
    
    file = request.files['video']
    
    # Save video file
    success, message, filepath = video_service.save_video_file(file, app.config['UPLOAD_FOLDER'])
    
    if not success:
        return jsonify({'success': False, 'message': message}), 400
    
    # Start processing for PARKING DETECTION (not plates)
    success, message = video_service.process_video_file(filepath, mode='parking')
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Video uploaded successfully and parking detection started',
            'filepath': filepath
        })
    else:
        return jsonify({'success': False, 'message': f'Error: {message}'}), 500


@app.route('/api/parking_statistics')
def api_parking_statistics():
    """API endpoint for parking statistics"""
    stats = dashboard_service.get_parking_statistics()
    return jsonify(stats)


# ============================================================================
# PARKING SPACES ROUTES (ROI Configuration)
# ============================================================================

@app.route('/parking_spaces')
def parking_spaces():
    """ROI Configuration visualizer page"""
    roi_config = parking_space_service.load_config()
    return render_template('parking_spaces.html', roi_config=roi_config)


@app.route('/upload_roi_config', methods=['POST'])
def upload_roi_config():
    """Upload and save ROI configuration JSON"""
    try:
        if 'config_file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['config_file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Process upload
        success, message, config = parking_space_service.upload_config_file(file)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'roi_count': len(config) if config else 0
            })
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/upload_cctv_frame', methods=['POST'])
def upload_cctv_frame():
    """Upload CCTV frame image"""
    try:
        if 'frame_file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['frame_file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Process upload
        success, message, filepath = parking_space_service.upload_frame(file)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'frame_path': os.path.basename(filepath) if filepath else None
            })
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/generate_roi_preview', methods=['POST'])
def generate_roi_preview():
    """Generate preview image with ROI overlays"""
    try:
        success, message, preview_path = parking_space_service.generate_preview()
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'preview_url': url_for('get_roi_preview')
            })
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/roi_preview')
def get_roi_preview():
    """Serve the ROI preview image"""
    preview_file = os.path.join(app.config['UPLOAD_FOLDER'], 'roi_preview.jpg')
    if os.path.exists(preview_file):
        return send_from_directory(app.config['UPLOAD_FOLDER'], 'roi_preview.jpg')
    else:
        return jsonify({'error': 'Preview not found'}), 404


@app.route('/api/roi_summary')
def api_roi_summary():
    """API endpoint for ROI configuration summary"""
    summary = parking_space_service.get_config_summary()
    return jsonify(summary)


# ============================================================================
# VIDEO PROCESSING ROUTES (License Plate Detection & OCR)
# ============================================================================

@app.route('/video_upload')
def video_upload():
    """Video upload page for license plate detection"""
    return render_template('video_upload.html')


@app.route('/upload_video_for_plates', methods=['POST'])
def upload_video_for_plates():
    """Handle video file upload for LICENSE PLATE detection (not parking)"""
    if 'video' not in request.files:
        return jsonify({'success': False, 'message': 'No video file selected'}), 400
    
    file = request.files['video']
    
    # Save video file
    success, message, filepath = video_service.save_video_file(file, app.config['UPLOAD_FOLDER'])
    
    if not success:
        return jsonify({'success': False, 'message': message}), 400
    
    # Start processing for LICENSE PLATE detection
    success, message = video_service.process_video_file(filepath, mode='plates')
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Video uploaded successfully and license plate detection started',
            'filepath': filepath
        })
    else:
        return jsonify({'success': False, 'message': f'Error: {message}'}), 500


@app.route('/api/processing_status')
def api_processing_status():
    """Get current video processing status"""
    status = video_service.get_processing_status()
    return jsonify(status)


@app.route('/api/detected_plates')
def api_detected_plates():
    """Get list of detected license plates from current session"""
    plates = video_service.get_detected_plates()
    return jsonify({'plates': plates})


@app.route('/api/plate_image/<int:plate_id>')
def api_plate_image(plate_id):
    """Serve cropped license plate image"""
    plate_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'detected_plates')
    
    # Find the file matching the plate_id (it may have a frame number suffix)
    pattern = os.path.join(plate_folder, f'plate_{plate_id}_*.jpg')
    matching_files = glob.glob(pattern)
    
    if matching_files:
        filename = os.path.basename(matching_files[0])
        return send_from_directory(plate_folder, filename)
    else:
        # Try without frame number suffix
        filename = f'plate_{plate_id}.jpg'
        if os.path.exists(os.path.join(plate_folder, filename)):
            return send_from_directory(plate_folder, filename)
        
        return jsonify({'error': 'Plate image not found'}), 404


# ============================================================================
# REPORTS ROUTES
# ============================================================================

@app.route('/reports')
def reports():
    """Reports and analytics page"""
    daily_revenue = report_service.get_daily_revenue(days=7)
    hourly_occupancy = report_service.get_hourly_occupancy()
    top_vehicles = report_service.get_top_vehicles(limit=10)
    
    return render_template('reports.html',
                         daily_revenue=daily_revenue,
                         hourly_occupancy=hourly_occupancy,
                         top_vehicles=top_vehicles)


@app.route('/api/revenue_summary')
def api_revenue_summary():
    """API endpoint for revenue summary"""
    days = request.args.get('days', 7, type=int)
    summary = report_service.get_revenue_summary(days)
    return jsonify(summary)


# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print('Client connected')
    emit('status', {'msg': 'Connected to Smart Parking System'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('Client disconnected')


def broadcast_parking_update(data):
    """Broadcast parking space updates to all connected clients"""
    socketio.emit('parking_update', data)


def broadcast_detection(detection_data):
    """Broadcast new vehicle detection to all connected clients"""
    socketio.emit('new_detection', detection_data)


def broadcast_plate_detection(plate_data):
    """Broadcast license plate detection"""
    socketio.emit('plate_detected', plate_data)


# ============================================================================
# INITIALIZATION
# ============================================================================

# Set broadcast functions
video_service.set_broadcast_functions(broadcast_parking_update, broadcast_detection, broadcast_plate_detection)
parking_manager.set_broadcast_function(broadcast_parking_update)