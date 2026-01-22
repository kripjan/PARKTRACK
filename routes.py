"""
Routes module - Dashboard with video upload, separate Parking Spaces page, Plate Detector
"""
import os
import json
import glob
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_socketio import emit
from werkzeug.utils import secure_filename
from app import app, socketio
from models import ParkingSpace, Vehicle, DetectionLog
from services import DashboardService, VideoService, ReportService, ParkingSpaceService
from parking_manager import ParkingManager

from image_plate_detector import ImagePlateDetector

image_plate_detector = ImagePlateDetector(app.config['UPLOAD_FOLDER'])

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

@app.route('/download_processed_video/<filename>')
def download_processed_video(filename):
    """Download processed parking video"""
    safe_filename = secure_filename(filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
    
    if os.path.exists(filepath):
        return send_from_directory(
            app.config['UPLOAD_FOLDER'], 
            safe_filename, 
            as_attachment=True,
            download_name=f'parking_output_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
        )
    else:
        return jsonify({'error': 'Video file not found'}), 404


@app.route('/api/parking_config_status')
def api_parking_config_status():
    """Check if parking detection is properly configured"""
    try:
        is_configured = video_service.parking_detector.is_configured()
        slot_count = video_service.parking_detector.get_slot_count()
        
        status = {
            'configured': is_configured,
            'slot_count': slot_count,
            'has_homography': video_service.parking_detector.H is not None,
            'has_slots': video_service.parking_detector.parking_slots is not None,
            'database_spaces': ParkingSpace.query.count()
        }
        
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'configured': False,
            'error': str(e)
        }), 500

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
# PLATE DETECTOR ROUTES (License Plate Detection & OCR)
# ============================================================================

@app.route('/plate_detector')
def plate_detector():
    """Plate Detector page - image-based detection with manual correction"""
    recent_detections = DetectionLog.query.filter_by(
        detection_type='license_plate'
    ).order_by(DetectionLog.timestamp.desc()).limit(20).all()
    
    return render_template('plate_detector.html', recent_detections=recent_detections)


@app.route('/upload_plate_image', methods=['POST'])
def upload_plate_image():
    """Handle image upload for plate detection"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No image file uploaded'}), 400
        
        file = request.files['image']
        detection_type = request.form.get('detection_type', 'entry')
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Validate file type
        allowed_extensions = {'jpg', 'jpeg', 'png', 'bmp'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({'success': False, 'message': 'Invalid file type. Use JPG, PNG, or BMP'}), 400
        
        # Save uploaded image
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'upload_{timestamp}_{filename}'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Process image
        result = image_plate_detector.process_image(filepath)
        
        if not result['success']:
            return jsonify({
                'success': False,
                'message': result['message']
            }), 400
        
        # Prepare response
        response_data = {
            'success': True,
            'message': result['message'],
            'original_image': url_for('serve_upload', filename=os.path.basename(filepath)),
            'plate_text': result['plate_text'],
            'timestamp': result['timestamp'],
            'detection_type': detection_type
        }
        
        # Add cropped plate URL if available
        if result['cropped_plate']:
            response_data['cropped_plate'] = url_for('serve_upload', 
                filename=f"detected_plates/{os.path.basename(result['cropped_plate'])}")
            response_data['cropped_plate_path'] = result['cropped_plate']
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Error processing plate image: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/save_corrected_plate', methods=['POST'])
def save_corrected_plate():
    """Save manually corrected plate to database"""
    try:
        data = request.get_json()
        
        detected_text = data.get('detected_text', '')
        corrected_text = data.get('corrected_text', '')
        cropped_plate_path = data.get('cropped_plate_path', '')
        detection_type = data.get('detection_type', 'entry')
        
        if not corrected_text:
            return jsonify({'success': False, 'message': 'No plate text provided'}), 400
        
        # Convert URL path back to file path
        if cropped_plate_path.startswith('/uploads/'):
            cropped_plate_path = os.path.join(
                app.config['UPLOAD_FOLDER'], 
                cropped_plate_path.replace('/uploads/', '')
            )
        
        # Save to database
        success, message = image_plate_detector.save_to_database(
            detected_text, 
            cropped_plate_path, 
            corrected_text
        )
        
        if success:
            # Handle entry/exit logic
            if detection_type == 'entry':
                parking_manager.handle_vehicle_detection(corrected_text)
            elif detection_type == 'exit':
                parking_manager.handle_vehicle_detection(corrected_text)
            
            return jsonify({
                'success': True,
                'message': message,
                'plate_number': corrected_text,
                'detection_type': detection_type
            })
        else:
            return jsonify({'success': False, 'message': message}), 500
            
    except Exception as e:
        app.logger.error(f"Error saving corrected plate: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/recent_detections')
def api_recent_detections():
    """Get recent plate detections"""
    try:
        detections = DetectionLog.query.filter_by(
            detection_type='license_plate'
        ).order_by(DetectionLog.timestamp.desc()).limit(20).all()
        
        result = []
        for detection in detections:
            result.append({
                'id': detection.id,
                'license_plate': detection.license_plate,
                'confidence': detection.confidence,
                'timestamp': detection.timestamp.isoformat(),
                'frame_path': detection.frame_path
            })
        
        return jsonify({'success': True, 'detections': result})
    except Exception as e:
        app.logger.error(f"Error fetching recent detections: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


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