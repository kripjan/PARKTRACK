import logging
import os
import cv2
import numpy as np
from datetime import datetime

try:
    from ultralytics import YOLO
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False


class ImagePlateDetector:
    """
    Image-based license plate detector with Nepali OCR support
    Detects plate, crops it, and performs character recognition
    """
    
    def __init__(self, upload_folder='uploads'):
        self.logger = logging.getLogger(__name__)
        self.upload_folder = upload_folder
        self.plates_folder = os.path.join(upload_folder, 'detected_plates')
        
        # Ensure folders exist
        os.makedirs(self.plates_folder, exist_ok=True)
        
        # Load models
        self.plate_detector = None
        self.ocr_model = None
        
        if CV_AVAILABLE:
            try:
                # Load license plate detection model
                plate_model_path = 'model/license_plate.pt'
                if os.path.exists(plate_model_path):
                    self.plate_detector = YOLO(plate_model_path)
                    self.logger.info("License plate detection model loaded")
                else:
                    self.logger.warning(f"Plate detection model not found: {plate_model_path}")
                
                # Load Nepali OCR model
                ocr_model_path = 'model/nepali_lp.pt'
                if os.path.exists(ocr_model_path):
                    self.ocr_model = YOLO(ocr_model_path)
                    self.logger.info("Nepali OCR model loaded")
                else:
                    self.logger.warning(f"OCR model not found: {ocr_model_path}")
                    
            except Exception as e:
                self.logger.error(f"Error loading models: {e}")
        else:
            self.logger.warning("Computer vision libraries not available")
    
    def detect_and_crop_plate(self, image_path):
        """
        Detect license plate in image and crop it
        
        Args:
            image_path (str): Path to input image
            
        Returns:
            tuple: (success, cropped_plate_path, plate_bbox, message)
        """
        try:
            if not CV_AVAILABLE or self.plate_detector is None:
                return False, None, None, "Plate detection model not available"
            
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                return False, None, None, "Failed to read image"
            
            # Detect license plates
            results = self.plate_detector(image, conf=0.3, verbose=False)
            
            if len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
                return False, None, None, "No license plate detected in image"
            
            # Get the first (most confident) detection
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()
            
            # Get highest confidence detection
            best_idx = np.argmax(confidences)
            x1, y1, x2, y2 = map(int, boxes[best_idx])
            confidence = float(confidences[best_idx])
            
            # Crop the plate region with some padding
            padding = 10
            h, w = image.shape[:2]
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(w, x2 + padding)
            y2 = min(h, y2 + padding)
            
            cropped_plate = image[y1:y2, x1:x2]
            
            # Save cropped plate
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            cropped_filename = f'plate_{timestamp}.jpg'
            cropped_path = os.path.join(self.plates_folder, cropped_filename)
            cv2.imwrite(cropped_path, cropped_plate)
            
            self.logger.info(f"License plate detected and cropped: {cropped_filename} (conf: {confidence:.2f})")
            
            return True, cropped_path, (x1, y1, x2, y2), f"Plate detected with {confidence*100:.1f}% confidence"
            
        except Exception as e:
            self.logger.error(f"Error detecting plate: {e}")
            return False, None, None, str(e)
    
    def recognize_characters(self, cropped_plate_path):
        """
        Recognize characters from cropped license plate using Nepali OCR model
        
        Args:
            cropped_plate_path (str): Path to cropped plate image
            
        Returns:
            tuple: (success, plate_text, character_details, message)
        """
        try:
            if not CV_AVAILABLE or self.ocr_model is None:
                return False, "", [], "OCR model not available"
            
            # Read cropped plate
            plate_img = cv2.imread(cropped_plate_path)
            if plate_img is None:
                return False, "", [], "Failed to read cropped plate"
            
            # Perform OCR detection
            results = self.ocr_model(plate_img, conf=0.25, verbose=False)
            
            if len(results) == 0 or results[0].boxes is None or len(results[0].boxes) == 0:
                return False, "", [], "No characters detected"
            
            # Get all detected characters with their positions
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()
            classes = results[0].boxes.cls.cpu().numpy()
            
            # Get class names from model
            class_names = results[0].names
            
            # Create character list with positions
            characters = []
            for i, (box, conf, cls) in enumerate(zip(boxes, confidences, classes)):
                x1, y1, x2, y2 = box
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                
                char = class_names[int(cls)]
                
                characters.append({
                    'char': char,
                    'confidence': float(conf),
                    'x': float(center_x),
                    'y': float(center_y),
                    'box': [float(x1), float(y1), float(x2), float(y2)]
                })
            
            # Sort characters from left to right, top to bottom
            # First sort by y-coordinate (top to bottom) with some tolerance
            # Then sort by x-coordinate (left to right)
            characters.sort(key=lambda c: (c['y'] // 20, c['x']))
            
            # Build plate text
            plate_text = ''.join([c['char'] for c in characters])
            
            self.logger.info(f"OCR detected: {plate_text}")
            
            return True, plate_text, characters, f"Recognized {len(characters)} characters"
            
        except Exception as e:
            self.logger.error(f"Error performing OCR: {e}")
            return False, "", [], str(e)
    
    def process_image(self, image_path):
        """
        Complete pipeline: detect plate, crop, and perform OCR
        
        Args:
            image_path (str): Path to input image
            
        Returns:
            dict: Complete detection results
        """
        result = {
            'success': False,
            'original_image': image_path,
            'cropped_plate': None,
            'plate_text': '',
            'characters': [],
            'bbox': None,
            'timestamp': datetime.now().isoformat(),
            'message': ''
        }
        
        try:
            # Step 1: Detect and crop plate
            success, cropped_path, bbox, msg = self.detect_and_crop_plate(image_path)
            
            if not success:
                result['message'] = msg
                return result
            
            result['cropped_plate'] = cropped_path
            result['bbox'] = bbox
            
            # Step 2: Perform OCR on cropped plate
            success, plate_text, characters, ocr_msg = self.recognize_characters(cropped_path)
            
            if not success:
                result['message'] = f"Plate detected but OCR failed: {ocr_msg}"
                result['success'] = True  # Still successful because plate was detected
                return result
            
            result['plate_text'] = plate_text
            result['characters'] = characters
            result['success'] = True
            result['message'] = f"Successfully detected plate: {plate_text}"
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in process_image: {e}")
            result['message'] = str(e)
            return result
    
    def save_to_database(self, plate_text, cropped_plate_path, corrected_text=None):
        """
        Save detected plate to database
        
        Args:
            plate_text (str): Auto-detected plate text
            cropped_plate_path (str): Path to cropped image
            corrected_text (str, optional): Manually corrected text
            
        Returns:
            tuple: (success, message)
        """
        try:
            from app import db
            from models import Vehicle, DetectionLog
            from datetime import datetime
            
            # Use corrected text if provided, otherwise use detected text
            final_plate_text = corrected_text if corrected_text else plate_text
            
            if not final_plate_text:
                return False, "No plate text to save"
            
            # Find or create vehicle
            vehicle = Vehicle.query.filter_by(license_plate=final_plate_text).first()
            
            if not vehicle:
                vehicle = Vehicle(
                    license_plate=final_plate_text,
                    first_seen=datetime.now(),
                    last_seen=datetime.now(),
                    total_visits=1
                )
                db.session.add(vehicle)
            else:
                vehicle.last_seen = datetime.now()
                vehicle.total_visits += 1
            
            # Create detection log
            detection_log = DetectionLog(
                detection_type='license_plate',
                license_plate=final_plate_text,
                confidence=1.0 if corrected_text else 0.8,
                frame_path=os.path.basename(cropped_plate_path),
                timestamp=datetime.now()
            )
            db.session.add(detection_log)
            
            db.session.commit()
            
            self.logger.info(f"Saved plate to database: {final_plate_text}")
            return True, f"Plate {final_plate_text} saved successfully"
            
        except Exception as e:
            self.logger.error(f"Error saving to database: {e}")
            db.session.rollback()
            return False, str(e)