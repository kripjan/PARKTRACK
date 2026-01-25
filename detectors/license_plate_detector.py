"""
Unified License Plate Detector
Handles both image uploads and video frame processing
"""
import logging
import os
import cv2
import numpy as np
from datetime import datetime
from sklearn.cluster import KMeans

try:
    from ultralytics import YOLO
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False


class LicensePlateDetector:
    """
    Unified license plate detector with Nepali OCR support
    Works with both uploaded images and video frame ROIs
    """
    
    def __init__(self, upload_folder='uploads'):
        self.logger = logging.getLogger(__name__)
        self.upload_folder = upload_folder
        self.plates_folder = os.path.join(upload_folder, 'detected_plates')
        
        # Ensure folders exist
        os.makedirs(self.plates_folder, exist_ok=True)
        
        # Initialize models
        self.plate_detector = None
        self.ocr_model = None
        
        if CV_AVAILABLE:
            self._load_models()
        else:
            self.logger.warning("Computer vision libraries not available")
    
    def _load_models(self):
        """Load YOLO models once during initialization"""
        try:
            # Plate detection model
            plate_model_path = 'model/license_plate.pt'
            if os.path.exists(plate_model_path):
                self.plate_detector = YOLO(plate_model_path)
                self.logger.info("✓ License plate detection model loaded")
            else:
                self.logger.error(f"✗ Plate model not found: {plate_model_path}")
            
            # Nepali OCR model
            ocr_model_path = 'model/nepali_lp.pt'
            if os.path.exists(ocr_model_path):
                self.ocr_model = YOLO(ocr_model_path)
                self.logger.info("✓ Nepali OCR model loaded")
            else:
                self.logger.error(f"✗ OCR model not found: {ocr_model_path}")
                
        except Exception as e:
            self.logger.error(f"Error loading models: {e}")
    
    # ============================================================
    # PUBLIC API - Two entry points
    # ============================================================
    
    def detect_from_image(self, image_path, save_cropped=True):
        """
        Detect license plate from uploaded image file
        
        Args:
            image_path (str): Path to uploaded image
            save_cropped (bool): Whether to save cropped plate
            
        Returns:
            dict: {
                'success': bool,
                'plate_text': str,
                'confidence': float,
                'cropped_plate_path': str,
                'bbox': tuple,
                'characters': list,
                'message': str
            }
        """
        try:
            # Read image from file
            image = cv2.imread(image_path)
            if image is None:
                return self._error_result("Failed to read image file")
            
            # Process the image
            return self._process(image, save_cropped=save_cropped)
            
        except Exception as e:
            self.logger.error(f"Error in detect_from_image: {e}")
            return self._error_result(str(e))
    
    def detect_from_roi(self, vehicle_roi):
        """
        Detect license plate from video frame ROI
        
        Args:
            vehicle_roi (numpy.ndarray): Cropped vehicle region from video
            
        Returns:
            str or None: Detected plate text or None
        """
        try:
            if vehicle_roi is None or vehicle_roi.size == 0:
                return None
            
            # Process the ROI (simpler return for video processing)
            result = self._process(vehicle_roi, save_cropped=False)
            
            return result['plate_text'] if result['success'] else None
            
        except Exception as e:
            self.logger.error(f"Error in detect_from_roi: {e}")
            return None
    
    # ============================================================
    # CORE PROCESSING - Shared logic
    # ============================================================
    
    def _process(self, image, save_cropped=True):
        """
        Core processing pipeline (used by both entry points)
        
        Steps:
        1. Detect plate bounding box
        2. Crop plate region
        3. Perform OCR on cropped plate
        4. Return results
        
        Args:
            image (numpy.ndarray): Input image
            save_cropped (bool): Whether to save cropped plate
            
        Returns:
            dict: Detection results
        """
        result = {
            'success': False,
            'plate_text': '',
            'confidence': 0.0,
            'cropped_plate_path': None,
            'bbox': None,
            'characters': [],
            'timestamp': datetime.now().isoformat(),
            'message': ''
        }
        
        # Check if models are loaded
        if not CV_AVAILABLE or self.plate_detector is None:
            result['message'] = "Plate detection model not available"
            return result
        
        # Step 1: Detect plate location
        plate_bbox, plate_confidence = self._detect_plate_bbox(image)
        
        if plate_bbox is None:
            result['message'] = "No license plate detected in image"
            return result
        
        # Step 2: Crop plate region
        cropped_plate = self._crop_plate(image, plate_bbox)
        
        if cropped_plate is None:
            result['message'] = "Failed to crop plate region"
            return result
        
        # Step 3: Save cropped plate (if requested)
        cropped_path = None
        if save_cropped:
            cropped_path = self._save_cropped_plate(cropped_plate)
            result['cropped_plate_path'] = cropped_path
        
        # Step 4: Perform OCR
        plate_text, characters = self._perform_ocr(cropped_plate)
        
        # Step 5: Build result
        result.update({
            'success': True,
            'plate_text': plate_text,
            'confidence': plate_confidence,
            'bbox': plate_bbox,
            'characters': characters,
            'message': f"Successfully detected: {plate_text}" if plate_text else "Plate detected but OCR failed"
        })
        
        return result
    
    # ============================================================
    # INTERNAL METHODS - Processing steps
    # ============================================================
    
    def _detect_plate_bbox(self, image):
        """
        Detect license plate bounding box in image
        
        Returns:
            tuple: (bbox, confidence) or (None, 0.0)
        """
        try:
            results = self.plate_detector(image, conf=0.3, verbose=False)
            
            if len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
                return None, 0.0
            
            # Get highest confidence detection
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()
            
            best_idx = np.argmax(confidences)
            bbox = boxes[best_idx]
            confidence = float(confidences[best_idx])
            
            return tuple(map(int, bbox)), confidence
            
        except Exception as e:
            self.logger.error(f"Error detecting plate bbox: {e}")
            return None, 0.0
    
    def _crop_plate(self, image, bbox, padding=10):
        """
        Crop plate region from image with padding
        
        Args:
            image: Input image
            bbox: (x1, y1, x2, y2)
            padding: Pixels to add around bbox
            
        Returns:
            numpy.ndarray or None: Cropped plate image
        """
        try:
            x1, y1, x2, y2 = bbox
            h, w = image.shape[:2]
            
            # Add padding
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(w, x2 + padding)
            y2 = min(h, y2 + padding)
            
            cropped = image[y1:y2, x1:x2]
            
            return cropped if cropped.size > 0 else None
            
        except Exception as e:
            self.logger.error(f"Error cropping plate: {e}")
            return None
    
    def _save_cropped_plate(self, cropped_plate):
        """
        Save cropped plate to disk
        
        Returns:
            str: Path to saved file
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f'plate_{timestamp}.jpg'
            filepath = os.path.join(self.plates_folder, filename)
            
            cv2.imwrite(filepath, cropped_plate)
            self.logger.info(f"Saved cropped plate: {filename}")
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error saving cropped plate: {e}")
            return None
    
    def _perform_ocr(self, cropped_plate):
        """
        Perform OCR on cropped plate using Nepali model
        
        Returns:
            tuple: (plate_text, character_details)
        """
        if self.ocr_model is None:
            return '', []
        
        try:
            results = self.ocr_model(cropped_plate, conf=0.25, verbose=False)
            
            if len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
                return '', []
            
            # Extract characters with positions
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()
            classes = results[0].boxes.cls.cpu().numpy()
            class_names = results[0].names
            
            # Build character list
            characters = []
            for box, conf, cls in zip(boxes, confidences, classes):
                x1, y1, x2, y2 = box
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                
                characters.append({
                    'char': class_names[int(cls)],
                    'confidence': float(conf),
                    'x': float(center_x),
                    'y': float(center_y),
                    'box': [float(x1), float(y1), float(x2), float(y2)]
                })
            
            if len(characters) == 0:
                plate_text = ''
            else:
                # Extract y-centers of all characters
                y_centers = np.array([c['y'] for c in characters]).reshape(-1, 1)
                
                # Decide number of rows: 1 if y spread is small, else 2
                y_range = y_centers.max() - y_centers.min()
                avg_char_height = np.mean([c['box'][3] - c['box'][1] for c in characters])
                
                if y_range < 1.5 * avg_char_height:
                    # Single row plate: simple left-to-right sorting
                    characters.sort(key=lambda c: c['x'])
                    plate_text = ''.join([c['char'] for c in characters])
                else:
                    # Multi-row plate: cluster into 2 rows
                    n_rows = 2
                    kmeans = KMeans(n_clusters=n_rows, random_state=0, n_init=10).fit(y_centers)
                    labels = kmeans.labels_
                    
                    # Group characters into rows
                    rows = [[] for _ in range(n_rows)]
                    for c, label in zip(characters, labels):
                        rows[label].append(c)
                    
                    # Sort characters within each row left-to-right
                    for row in rows:
                        row.sort(key=lambda c: c['x'])
                    
                    # Sort rows top-to-bottom (by average y of row)
                    rows.sort(key=lambda r: np.mean([c['y'] for c in r]))
                    
                    # Build final plate text
                    plate_text = ''
                    for row in rows:
                        plate_text += ''.join([c['char'] for c in row])
            
            self.logger.info(f"OCR result: {plate_text}")
            return plate_text, characters
            
        except Exception as e:
            self.logger.error(f"Error performing OCR: {e}")
            return '', []
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def _error_result(self, message):
        """Create error result dict"""
        return {
            'success': False,
            'plate_text': '',
            'confidence': 0.0,
            'cropped_plate_path': None,
            'bbox': None,
            'characters': [],
            'timestamp': datetime.now().isoformat(),
            'message': message
        }
    
    def is_available(self):
        """Check if detector is ready to use"""
        return CV_AVAILABLE and self.plate_detector is not None and self.ocr_model is not None