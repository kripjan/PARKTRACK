"""
Parking Detector - Handles parking space occupancy detection using homography
Based on your existing video.py logic
"""
import os
import cv2
import numpy as np
import json
import logging
from shapely.geometry import Point, Polygon

try:
    from ultralytics import YOLO
    from deep_sort_realtime.deepsort_tracker import DeepSort
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False


class ParkingDetector:
    """Detects parking space occupancy using homography transformation"""
    
    def __init__(self, config_folder='uploads/parking_config'):
        self.logger = logging.getLogger(__name__)
        self.config_folder = config_folder
        
        # Initialize variables
        self.H = None  # Homography matrix
        self.H_inv = None  # Inverse homography
        self.parking_slots = None  # Slots in camera view
        self.schematic_slots = None  # Slots in bird's-eye view
        self.slot_polygons = None  # Shapely polygons for slots
        self.src_pts = None  # Source points for ROI
        self.schematic_size = None
        
        self.model = None
        self.tracker = None
        
        # Load configuration
        self.load_configuration()
        
    def load_configuration(self):
        """Load all configuration files"""
        try:
            # Check if config folder exists
            if not os.path.exists(self.config_folder):
                self.logger.warning(f"Config folder not found: {self.config_folder}")
                return False
            
            # Load homography matrices
            h_matrix_path = os.path.join(self.config_folder, 'homography_matrix.npy')
            h_inv_path = os.path.join(self.config_folder, 'homography_inv.npy')
            
            if os.path.exists(h_matrix_path):
                self.H = np.load(h_matrix_path)
                self.logger.info("Loaded homography matrix")
            
            if os.path.exists(h_inv_path):
                self.H_inv = np.load(h_inv_path)
                self.logger.info("Loaded inverse homography matrix")
            
            # Load camera slots
            camera_slots_path = os.path.join(self.config_folder, 'camera_slots.npy')
            if os.path.exists(camera_slots_path):
                self.parking_slots = np.load(camera_slots_path, allow_pickle=True)
                self.logger.info(f"Loaded {len(self.parking_slots)} parking slots (camera view)")
            
            # Load source points
            src_points_path = os.path.join(self.config_folder, 'src_points.json')
            if os.path.exists(src_points_path):
                with open(src_points_path, 'r') as f:
                    data = json.load(f)
                    self.src_pts = np.float32(data[0]['points'])
                    self.logger.info("Loaded source points")
            
            # Load schematic slots
            schematic_slots_path = os.path.join(self.config_folder, 'slots_points.json')
            if os.path.exists(schematic_slots_path):
                with open(schematic_slots_path, 'r') as f:
                    slot_data = json.load(f)
                    self.schematic_slots = [np.array(slot['points'], dtype=np.int32) for slot in slot_data]
                    self.logger.info(f"Loaded {len(self.schematic_slots)} schematic slots")
                    
                    # Create polygons for occupancy detection
                    self.slot_polygons = [Polygon(slot.reshape(-1, 2)) for slot in self.schematic_slots]
                    
                    # Calculate schematic canvas size
                    all_schematic_pts = np.vstack(self.schematic_slots)
                    max_x = int(np.max(all_schematic_pts[:, 0])) + 100  # margin
                    max_y = int(np.max(all_schematic_pts[:, 1])) + 100
                    self.schematic_size = (max_x, max_y)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            return False
    
    def initialize_models(self, model_path='model/yolov8s.pt', device='cuda'):
        """Initialize YOLO and DeepSORT models"""
        if not CV_AVAILABLE:
            self.logger.warning("CV libraries not available")
            return False
        
        try:
            # Load YOLO model
            if os.path.exists(model_path):
                self.model = YOLO(model_path).to(device)
                self.logger.info(f"YOLO model loaded from {model_path}")
            else:
                self.logger.warning(f"Model not found: {model_path}")
                return False
            
            # Initialize DeepSORT tracker
            self.tracker = DeepSort(max_age=30, embedder="osnet_x0_25", embedder_device=device)
            self.logger.info("DeepSORT tracker initialized")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing models: {e}")
            return False
    
    def process_frame(self, frame, frame_id):
        """
        Process a single frame for parking detection
        
        Args:
            frame: Input frame from video
            frame_id: Frame number
            
        Returns:
            tuple: (processed_frame, schematic_view, slot_status)
        """
        if self.model is None or self.tracker is None:
            self.logger.warning("Models not initialized")
            return frame, None, []
        
        try:
            # Object detection with YOLO
            results = self.model.track(frame, persist=True, classes=[2, 3, 5, 7], imgsz=416)
            detections = results[0].boxes.xyxy.cpu().numpy() if results[0].boxes else []
            
            # Prepare DeepSORT inputs
            track_inputs = []
            for box in detections:
                x1, y1, x2, y2 = map(int, box[:4])
                
                # Draw bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                
                # Draw center point
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)
                
                track_inputs.append(([x1, y1, x2 - x1, y2 - y1], 0.9, 'vehicle'))
            
            # Update tracker
            tracks = self.tracker.update_tracks(track_inputs, frame=frame)
            
            # Create schematic canvas
            schematic = np.ones((self.schematic_size[1], self.schematic_size[0], 3), dtype=np.uint8) * 255
            slot_status = [False] * len(self.parking_slots)
            
            # Draw source points polygon on frame
            if self.src_pts is not None:
                cv2.polylines(frame, [self.src_pts.astype(int)], isClosed=True, color=(255, 0, 0), thickness=2)
            
            # Map tracked vehicles to bird's-eye view
            for track in tracks:
                if not track.is_confirmed():
                    continue
                
                x, y, w, h = track.to_ltwh()
                cx, cy = int(x + w / 2), int(y + h / 2)
                
                # Transform to bird's-eye view
                pt = np.array([[[cx, cy]]], dtype=np.float32)
                mapped_pt = cv2.perspectiveTransform(pt, self.H)[0][0]
                
                # Draw on schematic
                cv2.circle(schematic, tuple(mapped_pt.astype(int)), 5, (0, 0, 255), -1)
                
                # Check which slot the vehicle is in
                for i, poly in enumerate(self.slot_polygons):
                    if poly.contains(Point(mapped_pt)):
                        slot_status[i] = True
            
            # Draw slots on camera frame
            for i, slot in enumerate(self.parking_slots):
                color = (0, 255, 0) if not slot_status[i] else (0, 0, 255)  # Green=free, Red=occupied
                corrected_slot = np.int32(slot)
                cv2.polylines(frame, [corrected_slot], True, color, 2)
                
                # Add slot number
                center = np.mean(corrected_slot, axis=0).astype(int)
                cv2.putText(frame, str(i + 1), tuple(center),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            
            # Draw slots on schematic
            for i, slot in enumerate(self.schematic_slots):
                color = (0, 255, 0) if not slot_status[i] else (0, 0, 255)
                cv2.fillPoly(schematic, [slot], color)
                cv2.polylines(schematic, [slot], True, (50, 50, 50), 2)
                
                # Add slot number
                center = np.mean(slot, axis=0).astype(int)
                cv2.putText(schematic, str(i + 1), tuple(center),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            
            # Add status text to schematic
            occupied_count = sum(slot_status)
            empty_count = len(slot_status) - occupied_count
            status_text = f"Occupied: {occupied_count}   Free: {empty_count}"
            cv2.putText(schematic, status_text, (20, 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (20, 20, 20), 3, cv2.LINE_AA)
            
            return frame, schematic, slot_status
            
        except Exception as e:
            self.logger.error(f"Error processing frame {frame_id}: {e}")
            return frame, None, []
    
    def is_configured(self):
        """Check if parking detector is properly configured"""
        return (self.H is not None and 
                self.parking_slots is not None and 
                self.schematic_slots is not None)
    
    def get_slot_count(self):
        """Get total number of parking slots"""
        return len(self.parking_slots) if self.parking_slots is not None else 0
    
    def create_combined_output(self, frame, schematic):
        """
        Combine camera view and schematic view side-by-side
        
        Args:
            frame: Camera view
            schematic: Bird's-eye view
            
        Returns:
            Combined image
        """
        if schematic is None:
            return frame
        
        # Resize schematic to match frame height
        schematic_resized = cv2.resize(schematic, (frame.shape[1], frame.shape[0]))
        
        # Combine horizontally
        combined = np.hstack((frame, schematic_resized))
        
        return combined