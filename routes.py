"""
Routes module - handles HTTP routing with minimal logic
Business logic is delegated to service classes
"""
import os
import json
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
# DASHBOARD ROUTES
# ============================================================================

@app.route('/')
def dashboard():
    """Main dashboard with real-time parking status"""
    data = dashboard_service.get_dashboard_data()
    return render_template('dashboard.html', **data)


# ============================================================================
# VIDEO PROCESSING ROUTES
# ============================================================================

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
    
    # Save video file
    success, message, filepath = video_service.save_video_file(file, app.config['UPLOAD_FOLDER'])
    
    if not success:
        flash(message, 'error')
        return redirect(request.url)
    
    # Start processing
    success, message = video_service.process_video_file(filepath)
    
    if success:
        flash('Video uploaded successfully and processing started', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash(f'Error starting video processing: {message}', 'error')
        return redirect(request.url)


@app.route('/start_live_feed', methods=['POST'])
def start_live_feed():
    """Start processing live video feed"""
    camera_index = request.form.get('camera_index', 0, type=int)
    
    success, message = video_service.start_live_feed(camera_index)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('dashboard'))


@app.route('/stop_live_feed', methods=['POST'])
def stop_live_feed():
    """Stop processing live video feed"""
    success, message = video_service.stop_live_feed()
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('dashboard'))


# ============================================================================
# ROI CONFIGURATION ROUTES
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
        # Generate preview
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


@app.route('/cctv_frame')
def get_cctv_frame():
    """Serve the uploaded CCTV frame"""
    frame_file = os.path.join(app.config['UPLOAD_FOLDER'], 'cctv_frame.jpg')
    if os.path.exists(frame_file):
        return send_from_directory(app.config['UPLOAD_FOLDER'], 'cctv_frame.jpg')
    else:
        return jsonify({'error': 'Frame not found'}), 404


@app.route('/api/roi_summary')
def api_roi_summary():
    """API endpoint for ROI configuration summary"""
    summary = parking_space_service.get_config_summary()
    return jsonify(summary)


@app.route('/delete_roi_config', methods=['DELETE'])
def delete_roi_config():
    """Delete ROI configuration and associated files"""
    success, message = parking_space_service.delete_config()
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@app.route('/export_roi_config')
def export_roi_config():
    """Export ROI configuration as JSON"""
    success, config_json, message = parking_space_service.export_config()
    
    if success:
        return jsonify({
            'success': True,
            'config': json.loads(config_json),
            'message': message
        })
    else:
        return jsonify({'success': False, 'message': message}), 400


# ============================================================================
# REPORTS ROUTES
# ============================================================================

@app.route('/reports')
def reports():
    """Reports and analytics page"""
    # Get report data
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


@app.route('/api/vehicle_statistics')
def api_vehicle_statistics():
    """API endpoint for vehicle statistics"""
    stats = report_service.get_vehicle_statistics()
    return jsonify(stats)


@app.route('/api/detection_statistics')
def api_detection_statistics():
    """API endpoint for detection statistics"""
    days = request.args.get('days', 7, type=int)
    stats = report_service.get_detection_statistics(days)
    return jsonify(stats)


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


# ============================================================================
# INITIALIZATION
# ============================================================================

# Set broadcast functions for video service and parking manager
video_service.set_broadcast_functions(broadcast_parking_update, broadcast_detection)
parking_manager.set_broadcast_function(broadcast_parking_update)