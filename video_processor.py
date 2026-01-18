import threading
import time
import logging
from datetime import datetime
try:
    import cv2
    import numpy as np
    from ultralytics import YOLO
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False
    
from models import db
from models import DetectionLog, ParkingSpace, Vehicle, ParkingSession
from license_plate_detector import LicensePlateDetector
from parking_manager import ParkingManager

class VideoProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.is_processing = False
        self.current_thread = None
        self.broadcast_parking_update = None
        self.broadcast_detection = None
        
        # Initialize YOLO model for vehicle detection
        if CV_AVAILABLE:
            try:
                self.yolo_model = YOLO('model\\yolov8s.pt')  # Will download if not present
                self.logger.info("YOLO model loaded successfully")
            except Exception as e:
                self.logger.error(f"Failed to load YOLO model: {e}")
                self.yolo_model = None
        else:
            self.logger.warning("Computer vision libraries not available - using mock detection")
            self.yolo_model = None
        
        # Initialize license plate detector
        self.lp_detector = LicensePlateDetector()
        
        # Initialize parking manager
        self.parking_manager = ParkingManager()
        
        # Vehicle tracking variables
        self.vehicle_tracks = {}
        self.next_track_id = 1
        self.tracking_threshold = 50  # pixels
        
    def set_broadcast_functions(self, broadcast_parking_update, broadcast_detection):
        """Set broadcast functions for real-time updates"""
        self.broadcast_parking_update = broadcast_parking_update
        self.broadcast_detection = broadcast_detection
    
    def start_live_processing(self, camera_index=0):
        """Start processing live video feed from camera"""
        if self.is_processing:
            self.logger.warning("Video processing already in progress")
            return
        
        self.is_processing = True
        self.current_thread = threading.Thread(
            target=self._process_live_feed,
            args=(camera_index,),
            daemon=True
        )
        self.current_thread.start()
        self.logger.info(f"Started live video processing from camera {camera_index}")
    
    def stop_live_processing(self):
        """Stop live video processing"""
        self.is_processing = False
        if self.current_thread:
            self.current_thread.join(timeout=5)
        self.logger.info("Stopped live video processing")
    
    def process_video_file(self, filepath):
        """Process uploaded video file"""
        if self.is_processing:
            self.logger.warning("Video processing already in progress")
            return
        
        self.is_processing = True
        self.current_thread = threading.Thread(
            target=self._process_video_file,
            args=(filepath,),
            daemon=True
        )
        self.current_thread.start()
        self.logger.info(f"Started processing video file: {filepath}")
    
    def _process_live_feed(self, camera_index):
        """Internal method to process live video feed"""
        if not CV_AVAILABLE:
            self.logger.warning("Computer vision not available - using mock live feed")
            self._mock_live_feed()
            return
            
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            self.logger.error(f"Cannot open camera {camera_index}")
            self.is_processing = False
            return
        
        self.logger.info("Live video processing started")
        frame_count = 0
        
        try:
            while self.is_processing:
                ret, frame = cap.read()
                if not ret:
                    self.logger.warning("Failed to read frame from camera")
                    break
                
                # Process every 5th frame to reduce computational load
                if frame_count % 5 == 0:
                    self._process_frame(frame, frame_count)
                
                frame_count += 1
                time.sleep(0.1)  # Small delay to prevent overwhelming the system
                
        except Exception as e:
            self.logger.error(f"Error in live video processing: {e}")
        finally:
            cap.release()
            self.is_processing = False
            self.logger.info("Live video processing ended")
    
    def _process_video_file(self, filepath):
        """Internal method to process video file"""
        if not CV_AVAILABLE:
            self.logger.warning("Computer vision not available - using mock video processing")
            self._mock_video_processing(filepath)
            return
            
        cap = cv2.VideoCapture(filepath)
        if not cap.isOpened():
            self.logger.error(f"Cannot open video file: {filepath}")
            self.is_processing = False
            return
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.logger.info(f"Processing video: {total_frames} frames at {fps} FPS")
        
        frame_count = 0
        
        try:
            while self.is_processing and frame_count < total_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process frame
                self._process_frame(frame, frame_count)
                frame_count += 1
                
                # Update progress (every 100 frames)
                if frame_count % 100 == 0:
                    progress = (frame_count / total_frames) * 100
                    self.logger.info(f"Processing progress: {progress:.1f}%")
                
        except Exception as e:
            self.logger.error(f"Error processing video file: {e}")
        finally:
            cap.release()
            self.is_processing = False
            self.logger.info(f"Video file processing completed: {frame_count} frames processed")
    
    def _process_frame(self, frame, frame_number):
        """Process a single frame for vehicle detection and license plate recognition"""
        if self.yolo_model is None:
            return
        
        try:
            # Detect vehicles using YOLO
            results = self.yolo_model(frame, verbose=False)
            vehicles = []
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Filter for vehicle classes (car, truck, bus, motorcycle)
                        class_id = int(box.cls[0])
                        if class_id in [2, 5, 7, 3]:  # car, bus, truck, motorcycle in COCO dataset
                            confidence = float(box.conf[0])
                            if confidence > 0.5:  # Confidence threshold
                                x1, y1, x2, y2 = box.xyxy[0].tolist()
                                vehicles.append({
                                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                                    'confidence': confidence,
                                    'class_id': class_id
                                })
            
            # Update vehicle count and parking spaces
            self._update_parking_spaces(vehicles, frame)
            
            # Track vehicles and detect license plates
            self._track_vehicles(vehicles, frame)
            
            # Log detection
            with db.session.begin():
                detection = DetectionLog(
                    detection_type='detection',
                    vehicle_count=len(vehicles),
                    timestamp=datetime.utcnow()
                )
                db.session.add(detection)
                db.session.commit()
            
            # Broadcast real-time update
            if self.broadcast_detection:
                self.broadcast_detection({
                    'vehicle_count': len(vehicles),
                    'timestamp': datetime.utcnow().isoformat(),
                    'frame_number': frame_number
                })
                
        except Exception as e:
            self.logger.error(f"Error processing frame {frame_number}: {e}")
    
    def _update_parking_spaces(self, vehicles, frame):
        """Update parking space occupancy based on detected vehicles"""
        try:
            with db.session.begin():
                parking_spaces = ParkingSpace.query.all()
                
                for space in parking_spaces:
                    was_occupied = space.is_occupied
                    is_occupied = False
                    
                    # Check if any vehicle overlaps with this parking space
                    for vehicle in vehicles:
                        x1, y1, x2, y2 = vehicle['bbox']
                        
                        # Check for overlap with parking space
                        if self._rectangles_overlap(
                            (x1, y1, x2, y2),
                            (space.x1, space.y1, space.x2, space.y2)
                        ):
                            is_occupied = True
                            break
                    
                    space.is_occupied = is_occupied
                    
                    # If occupancy changed, broadcast update
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
    
    def _rectangles_overlap(self, rect1, rect2):
        """Check if two rectangles overlap"""
        x1_1, y1_1, x2_1, y2_1 = rect1
        x1_2, y1_2, x2_2, y2_2 = rect2
        
        return not (x2_1 < x1_2 or x2_2 < x1_1 or y2_1 < y1_2 or y2_2 < y1_1)
    
    def _track_vehicles(self, vehicles, frame):
        """Track vehicles across frames and detect license plates"""
        current_tracks = {}
        
        for vehicle in vehicles:
            bbox = vehicle['bbox']
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            
            # Find closest existing track
            closest_track_id = None
            min_distance = float('inf')
            
            for track_id, track_data in self.vehicle_tracks.items():
                prev_center = track_data['center']
                distance = np.sqrt((center_x - prev_center[0])**2 + (center_y - prev_center[1])**2)
                
                if distance < min_distance and distance < self.tracking_threshold:
                    min_distance = distance
                    closest_track_id = track_id
            
            # Assign track ID
            if closest_track_id is not None:
                track_id = closest_track_id
            else:
                track_id = self.next_track_id
                self.next_track_id += 1
            
            # Update track data
            current_tracks[track_id] = {
                'center': (center_x, center_y),
                'bbox': bbox,
                'last_seen': datetime.utcnow(),
                'vehicle_data': vehicle
            }
            
            # Detect license plate for new or long-unseen vehicles
            if (track_id not in self.vehicle_tracks or 
                (datetime.utcnow() - self.vehicle_tracks[track_id]['last_seen']).seconds > 30):
                
                self._detect_license_plate(frame, bbox, track_id)
        
        # Update vehicle tracks
        self.vehicle_tracks = current_tracks
    
    def _detect_license_plate(self, frame, bbox, track_id):
        """Detect license plate for a specific vehicle"""
        try:
            x1, y1, x2, y2 = bbox
            vehicle_roi = frame[y1:y2, x1:x2]
            
            # Use license plate detector
            license_plate = self.lp_detector.detect_license_plate(vehicle_roi)
            
            if license_plate:
                self.logger.info(f"Detected license plate: {license_plate} for track {track_id}")
                
                # Record vehicle entry/exit
                self.parking_manager.handle_vehicle_detection(license_plate)
                
                # Log detection
                with db.session.begin():
                    detection = DetectionLog(
                        detection_type='license_plate',
                        license_plate=license_plate,
                        confidence=0.8,  # Placeholder confidence
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(detection)
                    db.session.commit()
                
                # Broadcast detection
                if self.broadcast_detection:
                    self.broadcast_detection({
                        'type': 'license_plate',
                        'license_plate': license_plate,
                        'track_id': track_id,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
        except Exception as e:
            self.logger.error(f"Error detecting license plate: {e}")
    
    def _mock_live_feed(self):
        """Mock live feed for demonstration when CV libraries are not available"""
        self.logger.info("Starting mock live feed")
        frame_count = 0
        
        while self.is_processing:
            # Simulate processing every 5th frame
            if frame_count % 5 == 0:
                self._mock_process_frame(frame_count)
            
            frame_count += 1
            time.sleep(0.5)  # Slower for demo purposes
        
        self.is_processing = False
        self.logger.info("Mock live feed ended")
    
    def _mock_video_processing(self, filepath):
        """Mock video processing for demonstration"""
        import os
        self.logger.info(f"Starting mock processing of {os.path.basename(filepath)}")
        
        # Simulate processing 100 frames
        total_frames = 100
        frame_count = 0
        
        while self.is_processing and frame_count < total_frames:
            self._mock_process_frame(frame_count)
            frame_count += 1
            
            # Update progress every 10 frames
            if frame_count % 10 == 0:
                progress = (frame_count / total_frames) * 100
                self.logger.info(f"Mock processing progress: {progress:.1f}%")
            
            time.sleep(0.2)  # Simulate processing time
        
        self.is_processing = False
        self.logger.info(f"Mock video processing completed: {frame_count} frames processed")
    
    def _mock_process_frame(self, frame_number):
        """Mock frame processing that generates simulated vehicle detections"""
        import random
        
        # Simulate vehicle detection (random number between 0-5 vehicles)
        vehicle_count = random.randint(0, 5)
        
        # Simulate license plate detection occasionally
        if random.random() < 0.3:  # 30% chance
            mock_plates = ["ABC123", "XYZ789", "DEF456", "GHI012", "JKL345"]
            license_plate = random.choice(mock_plates)
            
            # Record mock detection
            self.parking_manager.handle_vehicle_detection(license_plate)
            
            # Log detection
            try:
                with db.session.begin():
                    detection = DetectionLog(
                        detection_type='license_plate',
                        license_plate=license_plate,
                        confidence=0.8,
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(detection)
                    db.session.commit()
            except Exception as e:
                self.logger.error(f"Error logging mock detection: {e}")
            
            # Broadcast detection
            if self.broadcast_detection:
                self.broadcast_detection({
                    'type': 'license_plate',
                    'license_plate': license_plate,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        # Log general detection
        try:
            with db.session.begin():
                detection = DetectionLog(
                    detection_type='detection',
                    vehicle_count=vehicle_count,
                    timestamp=datetime.utcnow()
                )
                db.session.add(detection)
                db.session.commit()
        except Exception as e:
            self.logger.error(f"Error logging mock detection: {e}")
        
        # Broadcast real-time update
        if self.broadcast_detection:
            self.broadcast_detection({
                'vehicle_count': vehicle_count,
                'timestamp': datetime.utcnow().isoformat(),
                'frame_number': frame_number
            })
