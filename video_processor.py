import threading
import time
import logging
import os
import base64
from datetime import datetime
from flask import current_app
from app import app, db
try:
    import cv2
    import numpy as np
    from ultralytics import YOLO
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False
    
from models import DetectionLog, ParkingSpace, Vehicle, ParkingSession
from license_plate_detector import LicensePlateDetector
from parking_manager import ParkingManager
from parking_detector import ParkingDetector


class VideoProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.is_processing = False
        self.current_thread = None
        self.current_frame = 0
        self.total_frames = 0
        
        # Broadcast functions
        self.broadcast_parking_update = None
        self.broadcast_detection = None
        self.broadcast_plate_detection = None
        
        # Initialize YOLO model for vehicle detection (for plate detection mode)
        if CV_AVAILABLE:
            try:
                self.yolo_model = YOLO('model/yolov8s.pt')
                self.logger.info("YOLO model loaded successfully")
            except Exception as e:
                self.logger.error(f"Failed to load YOLO model: {e}")
                self.yolo_model = None
        else:
            self.logger.warning("Computer vision libraries not available - using mock detection")
            self.yolo_model = None
        
        # Initialize parking detector (for parking space detection mode)
        self.parking_detector = ParkingDetector()
        
        # Initialize license plate detector
        self.lp_detector = LicensePlateDetector()
        
        # Initialize parking manager
        self.parking_manager = ParkingManager()
        
        # Detected plates storage
        self.detected_plates = []
        self.plates_folder = 'uploads/detected_plates'
        os.makedirs(self.plates_folder, exist_ok=True)
        
        # Processing statistics
        self.plates_detected = 0
        self.plates_recognized = 0
        
        # Processing mode
        self.processing_mode = 'parking'  # 'parking' or 'plates'
        
    def set_broadcast_functions(self, broadcast_parking_update, broadcast_detection, broadcast_plate_detection):
        """Set broadcast functions for real-time updates"""
        self.broadcast_parking_update = broadcast_parking_update
        self.broadcast_detection = broadcast_detection
        self.broadcast_plate_detection = broadcast_plate_detection
        self.parking_manager.set_broadcast_function(broadcast_parking_update)
    
    def process_video_file(self, filepath, mode='parking'):
        """
        Process uploaded video file
        
        Args:
            filepath: Path to video file
            mode: 'parking' for parking detection, 'plates' for license plate detection
        """
        if self.is_processing:
            self.logger.warning("Video processing already in progress")
            return
        
        self.is_processing = True
        self.processing_mode = mode
        
        # Reset statistics
        self.detected_plates = []
        self.plates_detected = 0
        self.plates_recognized = 0
        self.current_frame = 0
        
        self.current_thread = threading.Thread(
            target=self._process_video_file,
            args=(filepath,),
            daemon=True
        )
        self.current_thread.start()
        self.logger.info(f"Started processing video file: {filepath} in {mode} mode")
    
    def _process_video_file(self, filepath):
        """Internal method to process video file - WRAPPED IN APP CONTEXT"""
        # CRITICAL: Wrap entire processing in app context
        with app.app_context():
            if not CV_AVAILABLE:
                self.logger.warning("Computer vision not available - using mock video processing")
                self._mock_video_processing(filepath)
                return
            
            # Choose processing method based on mode
            if self.processing_mode == 'parking':
                self._process_video_parking(filepath)
            else:
                self._process_video_plates(filepath)
    
    def _process_video_parking(self, filepath):
        """Process video for parking space occupancy detection with live streaming"""
        if not self.parking_detector.is_configured():
            self.logger.error("Parking detector not configured. Please upload configuration files first.")
            self.is_processing = False
            
            if self.broadcast_detection:
                self.broadcast_detection({
                    'type': 'error',
                    'message': 'Parking configuration not found. Please configure parking spaces first.'
                })
            return
        
        # Initialize parking detector models
        if not self.parking_detector.initialize_models():
            self.logger.error("Failed to initialize parking detection models")
            self.is_processing = False
            
            if self.broadcast_detection:
                self.broadcast_detection({
                    'type': 'error',
                    'message': 'Failed to initialize parking detection models'
                })
            return
        
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            self.logger.error(f"Cannot open video file: {filepath}")
            self.is_processing = False
            
            if self.broadcast_detection:
                self.broadcast_detection({
                    'type': 'error',
                    'message': 'Failed to open video file'
                })
            return
        
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.logger.info(f"Processing parking video: {self.total_frames} frames at {fps} FPS")
        
        # Create output video
        output_path = filepath.replace('.mp4', '_parking_output.mp4')
        out = cv2.VideoWriter(
            output_path,
            cv2.VideoWriter_fourcc(*'mp4v'),
            fps,
            (width * 2, height)  # Double width for side-by-side view
        )
        
        frame_count = 0
        frame_skip = 2  # Process every 2nd frame
        stream_every = 5  # Stream every 5th processed frame to avoid overwhelming the browser
        
        try:
            while self.is_processing and frame_count < self.total_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                self.current_frame = frame_count
                
                # Process frame
                if frame_count % frame_skip == 0:
                    processed_frame, schematic, slot_status = self.parking_detector.process_frame(frame, frame_count)
                    
                    # Create combined output
                    combined = self.parking_detector.create_combined_output(processed_frame, schematic)
                    out.write(combined)
                    
                    # Update parking space database
                    if slot_status:
                        self._update_parking_spaces_from_slots(slot_status)
                    
                    # Stream frames to frontend
                    if frame_count % stream_every == 0 and self.broadcast_detection:
                        self._stream_parking_frames(processed_frame, schematic, slot_status)
                    
                    # Broadcast statistics update
                    if slot_status and self.broadcast_detection:
                        occupied = sum(slot_status)
                        available = len(slot_status) - occupied
                        
                        self.broadcast_detection({
                            'type': 'parking_stats_update',
                            'occupied': occupied,
                            'available': available,
                            'total': len(slot_status),
                            'vehicle_count': occupied
                        })
                
                frame_count += 1
                
                # Update progress
                if frame_count % 50 == 0:
                    progress = (frame_count / self.total_frames) * 100
                    self._broadcast_progress(progress, frame_count)
                
        except Exception as e:
            self.logger.error(f"Error processing parking video: {e}")
            
            if self.broadcast_detection:
                self.broadcast_detection({
                    'type': 'error',
                    'message': f'Processing error: {str(e)}'
                })
        finally:
            cap.release()
            out.release()
            self.is_processing = False
            
            # Broadcast completion
            self._broadcast_completion(frame_count, output_path)
            
            self.logger.info(f"Parking video processing completed: {frame_count} frames processed")
            self.logger.info(f"Output saved to: {output_path}")
    
    def _stream_parking_frames(self, camera_view, schematic_view, slot_status):
        """Stream current frames to frontend via WebSocket"""
        try:
            # Encode camera view to base64
            _, camera_buffer = cv2.imencode('.jpg', camera_view, [cv2.IMWRITE_JPEG_QUALITY, 70])
            camera_base64 = base64.b64encode(camera_buffer).decode('utf-8')
            
            # Encode schematic view to base64
            _, schematic_buffer = cv2.imencode('.jpg', schematic_view, [cv2.IMWRITE_JPEG_QUALITY, 70])
            schematic_base64 = base64.b64encode(schematic_buffer).decode('utf-8')
            
            # Calculate statistics
            occupied = sum(slot_status) if slot_status else 0
            total = len(slot_status) if slot_status else 0
            available = total - occupied
            
            # Broadcast frames
            if self.broadcast_detection:
                self.broadcast_detection({
                    'type': 'live_frame',
                    'camera_frame': camera_base64,
                    'schematic_frame': schematic_base64,
                    'stats': {
                        'total': total,
                        'occupied': occupied,
                        'available': available
                    },
                    'timestamp': datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error streaming frames: {e}")
    
    def _process_video_plates(self, filepath):
        """Process video for license plate detection (original logic)"""
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            self.logger.error(f"Cannot open video file: {filepath}")
            self.is_processing = False
            
            if self.broadcast_detection:
                self.broadcast_detection({
                    'type': 'error',
                    'message': 'Failed to open video file'
                })
            return
        
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.logger.info(f"Processing license plates: {self.total_frames} frames at {fps} FPS")
        
        frame_count = 0
        
        try:
            while self.is_processing and frame_count < self.total_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                self.current_frame = frame_count
                
                # Process every 5th frame for performance
                if frame_count % 5 == 0:
                    self._process_frame_for_plates(frame, frame_count)
                
                frame_count += 1
                
                # Update progress
                if frame_count % 50 == 0:
                    progress = (frame_count / self.total_frames) * 100
                    self._broadcast_progress(progress, frame_count)
                
        except Exception as e:
            self.logger.error(f"Error processing video file: {e}")
            
            if self.broadcast_detection:
                self.broadcast_detection({
                    'type': 'error',
                    'message': f'Processing error: {str(e)}'
                })
        finally:
            cap.release()
            self.is_processing = False
            
            # Broadcast completion
            self._broadcast_completion(frame_count)
            
            self.logger.info(f"Video file processing completed: {frame_count} frames processed")
    
    def _process_frame_for_plates(self, frame, frame_number):
        """Process a single frame for license plate detection"""
        if self.yolo_model is None:
            return
        
        try:
            # Detect vehicles using YOLO
            results = self.yolo_model(frame, verbose=False)
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Filter for vehicle classes
                        class_id = int(box.cls[0])
                        if class_id in [2, 5, 7, 3]:
                            confidence = float(box.conf[0])
                            if confidence > 0.5:
                                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                                
                                # Extract vehicle region
                                vehicle_roi = frame[y1:y2, x1:x2]
                                
                                # Detect license plate
                                self._detect_and_save_plate(vehicle_roi, frame, frame_number)
                
        except Exception as e:
            self.logger.error(f"Error processing frame {frame_number}: {e}")
    
    def _detect_and_save_plate(self, vehicle_roi, full_frame, frame_number):
        """Detect license plate in vehicle ROI and save it"""
        try:
            # Use license plate detector
            license_plate_text = self.lp_detector.detect_license_plate(vehicle_roi)
            
            if license_plate_text:
                self.plates_detected += 1
                
                # Save cropped plate image
                plate_filename = f'plate_{self.plates_detected}_{frame_number}.jpg'
                plate_path = os.path.join(self.plates_folder, plate_filename)
                
                cv2.imwrite(plate_path, vehicle_roi)
                
                # Determine if recognized
                is_recognized = license_plate_text and license_plate_text != 'Unknown'
                if is_recognized:
                    self.plates_recognized += 1
                
                # Create plate data
                plate_data = {
                    'plate_number': license_plate_text,
                    'confidence': 0.85,
                    'frame': frame_number,
                    'timestamp': datetime.utcnow().isoformat(),
                    'image_url': f'/api/plate_image/{self.plates_detected}',
                    'image_path': plate_path
                }
                
                self.detected_plates.append(plate_data)
                
                # Log to database (already in app context)
                try:
                    detection = DetectionLog(
                        detection_type='license_plate',
                        license_plate=license_plate_text,
                        confidence=0.85,
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(detection)
                    db.session.commit()
                except Exception as db_error:
                    self.logger.error(f"Database error: {db_error}")
                    db.session.rollback()
                
                # Broadcast
                if self.broadcast_plate_detection:
                    self.broadcast_plate_detection(plate_data)
                
                # Handle parking session
                if is_recognized:
                    self.parking_manager.handle_vehicle_detection(license_plate_text)
                
        except Exception as e:
            self.logger.error(f"Error detecting/saving plate: {e}")
    
    def _update_parking_spaces_from_slots(self, slot_status):
        """Update parking space occupancy in database from slot status"""
        try:
            # Already in app context from parent function
            # Get all parking spaces (assuming they match slot indices)
            spaces = ParkingSpace.query.order_by(ParkingSpace.id).all()
            
            for i, is_occupied in enumerate(slot_status):
                if i < len(spaces):
                    space = spaces[i]
                    was_occupied = space.is_occupied
                    space.is_occupied = is_occupied
                    
                    # Broadcast if changed
                    if was_occupied != is_occupied and self.broadcast_parking_update:
                        self.broadcast_parking_update({
                            'space_id': space.id,
                            'space_name': space.name,
                            'is_occupied': is_occupied,
                            'timestamp': datetime.utcnow().isoformat()
                        })
            
            db.session.commit()
            
        except Exception as e:
            self.logger.error(f"Error updating parking spaces: {e}")
            db.session.rollback()
    
    def _broadcast_progress(self, progress, frames_processed):
        """Broadcast processing progress"""
        if self.broadcast_detection:
            self.broadcast_detection({
                'type': 'processing_update',
                'progress': progress,
                'frames_processed': frames_processed,
                'plates_detected': self.plates_detected,
                'plates_recognized': self.plates_recognized
            })
    
    def _broadcast_completion(self, total_frames, output_path=None):
        """Broadcast processing completion"""
        if self.broadcast_detection:
            completion_data = {
                'type': 'processing_complete',
                'total_frames': total_frames,
                'plates_detected': self.plates_detected,
                'plates_recognized': self.plates_recognized
            }
            
            if output_path:
                completion_data['output_video'] = os.path.basename(output_path)
            
            self.broadcast_detection(completion_data)
    
    def _mock_video_processing(self, filepath):
        """Mock video processing when CV is not available"""
        self.logger.info("Running mock video processing")
        self.is_processing = False
    
    def get_detected_plates(self):
        """Get list of detected plates"""
        return self.detected_plates
    
    def stop_processing(self):
        """Stop video processing"""
        self.is_processing = False
        if self.current_thread:
            self.current_thread.join(timeout=5)
        self.logger.info("Stopped video processing")