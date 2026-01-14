"""
Routes module - handles HTTP routing with minimal logic
Business logic is delegated to service classes
"""
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_socketio import emit
from app import app, socketio
from services import DashboardService, ParkingSpaceService, VideoService, ReportService
from parking_manager import ParkingManager

# Initialize services
dashboard_service = DashboardService()
parking_space_service = ParkingSpaceService()
video_service = VideoService()
report_service = ReportService()
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
# PARKING SPACE ROUTES
# ============================================================================

@app.route('/parking_spaces')
def parking_spaces():
    """Parking space management page"""
    spaces = parking_space_service.get_all_spaces()
    return render_template('parking_spaces.html', spaces=spaces)


@app.route('/add_parking_space', methods=['POST'])
def add_parking_space():
    """Add a new parking space"""
    data = request.get_json()
    
    try:
        success, message, space = parking_space_service.create_space(
            name=data['name'],
            x1=data['x1'],
            y1=data['y1'],
            x2=data['x2'],
            y2=data['y2']
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'space_id': space.id if space else None
            })
        else:
            return jsonify({'success': False, 'message': message}), 400
            
    except KeyError as e:
        return jsonify({'success': False, 'message': f'Missing required field: {e}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@app.route('/delete_parking_space/<int:space_id>', methods=['DELETE'])
def delete_parking_space(space_id):
    """Delete a parking space"""
    success, message = parking_space_service.delete_space(space_id)
    
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 400


@app.route('/update_parking_space/<int:space_id>', methods=['PUT'])
def update_parking_space(space_id):
    """Update a parking space"""
    data = request.get_json()
    
    success, message, space = parking_space_service.update_space(
        space_id=space_id,
        name=data.get('name'),
        x1=data.get('x1'),
        y1=data.get('y1'),
        x2=data.get('x2'),
        y2=data.get('y2')
    )
    
    if success:
        return jsonify({'success': True, 'message': message})
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