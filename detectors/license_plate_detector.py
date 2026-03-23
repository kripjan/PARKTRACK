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

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


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
        self.easyocr_reader = None
        
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
                self.logger.info("âœ“ License plate detection model loaded")
            else:
                self.logger.error(f"âœ— Plate model not found: {plate_model_path}")
            
            # Nepali OCR model
            ocr_model_path = 'model/nepali_lp.pt'
            if os.path.exists(ocr_model_path):
                self.ocr_model = YOLO(ocr_model_path)
                self.logger.info("âœ“ Nepali OCR model loaded")
            else:
                self.logger.error(f"âœ— OCR model not found: {ocr_model_path}")
                
        except Exception as e:
            self.logger.error(f"Error loading models: {e}")
    
    def _get_easyocr_reader(self):
        """Lazy-load EasyOCR reader (English only, for embossed plates)"""
        if self.easyocr_reader is not None:
            return self.easyocr_reader
        
        if not EASYOCR_AVAILABLE:
            self.logger.error("EasyOCR not installed. Run: pip install easyocr")
            return None
        
        try:
            self.logger.info("Loading EasyOCR reader (first load may take a moment)...")
            self.easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            self.logger.info("✔ EasyOCR reader loaded")
            return self.easyocr_reader
        except Exception as e:
            self.logger.error(f"Error loading EasyOCR: {e}")
            return None
    
    def detect_from_image(self, image_path, save_cropped=True, is_embossed=False):
        """
        Detect license plate from uploaded image file
        
        Args:
            image_path (str): Path to uploaded image
            save_cropped (bool): Whether to save cropped plate
            is_embossed (bool): Use EasyOCR for English embossed plates
            
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
            return self._process(image, save_cropped=save_cropped, is_embossed=is_embossed)
            
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
    
    def _process(self, image, save_cropped=True, is_embossed=False):
        """
        Core processing pipeline (used by both entry points)
        
        Steps:
        1. Detect plate bounding box
        2. Crop plate region
        3. Perform OCR on cropped plate (EasyOCR for embossed, Nepali model otherwise)
        4. Return results
        
        Args:
            image (numpy.ndarray): Input image
            save_cropped (bool): Whether to save cropped plate
            is_embossed (bool): Use EasyOCR for English embossed plates
            
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
            'message': '',
            'ocr_engine': 'easyocr' if is_embossed else 'nepali'
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
        
        # Step 4: Perform OCR — branch based on plate type
        if is_embossed:
            plate_text, characters = self._perform_easyocr(cropped_plate)
        else:
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

            # -------- EXTRACT DETECTIONS --------
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()
            classes = results[0].boxes.cls.cpu().numpy()
            class_names = results[0].names

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
                    'top_y': float(y1),   # IMPORTANT FOR ROW CLUSTERING
                    'box': [float(x1), float(y1), float(x2), float(y2)]
                })

            if len(characters) == 0:
                return '', []

            # -------- CHECK SINGLE VS TWO ROW --------
            y_vals = np.array([c['top_y'] for c in characters])
            h_vals = np.array([c['box'][3] - c['box'][1] for c in characters])

            y_range = y_vals.max() - y_vals.min()
            avg_h = np.mean(h_vals)

            # -------- SINGLE ROW --------
            if y_range < 0.8 * avg_h:
                # Single row - just sort left to right
                characters.sort(key=lambda c: c['x'])
                plate_text = ''.join(c['char'] for c in characters)

            # -------- TWO ROW (USE Y-THRESHOLD, NOT KMEANS) --------
            else:
                # Find the midpoint Y value
                y_mid = (y_vals.min() + y_vals.max()) / 2
                
                # Split into rows based on Y position
                top_row = [c for c in characters if c['top_y'] < y_mid]
                bottom_row = [c for c in characters if c['top_y'] >= y_mid]
                
                # Sort each row left to right
                top_row.sort(key=lambda c: c['x'])
                bottom_row.sort(key=lambda c: c['x'])
                
                # Concatenate without space: top row first, then bottom row
                plate_text = ''.join(c['char'] for c in top_row) + ''.join(c['char'] for c in bottom_row)

            self.logger.info(f"OCR result: {plate_text}")
            return plate_text, characters

        except Exception as e:
            self.logger.error(f"Error performing OCR: {e}")
            return '', []

    
    def _perform_easyocr(self, cropped_plate):
        """
        Perform OCR on embossed plate using EasyOCR (English characters)

        Returns:
            tuple: (plate_text, character_details)
        """
        reader = self._get_easyocr_reader()
        if reader is None:
            self.logger.warning("EasyOCR not available, falling back to Nepali OCR")
            return self._perform_ocr(cropped_plate)

        try:
            # Preprocess: convert to grayscale + slight upscale for better accuracy
            gray = cv2.cvtColor(cropped_plate, cv2.COLOR_BGR2GRAY)
            scale = max(1.0, 200 / gray.shape[0])  # ensure at least 200px height
            if scale > 1.0:
                gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            
            # EasyOCR expects BGR or RGB; pass grayscale as-is
            results = reader.readtext(gray, detail=1, paragraph=False,
                                      allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-')

            if not results:
                return '', []

            # Sort detections left-to-right (by x center of bounding box)
            results.sort(key=lambda r: (r[0][0][0] + r[0][2][0]) / 2)

            characters = []
            texts = []
            for (bbox_pts, text, conf) in results:
                # bbox_pts: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                x_coords = [p[0] for p in bbox_pts]
                y_coords = [p[1] for p in bbox_pts]
                center_x = sum(x_coords) / 4
                center_y = sum(y_coords) / 4

                clean = text.strip().upper()
                if clean:
                    texts.append(clean)
                    characters.append({
                        'char': clean,
                        'confidence': float(conf),
                        'x': float(center_x),
                        'y': float(center_y),
                    })

            plate_text = ''.join(texts)
            self.logger.info(f"EasyOCR result: {plate_text}")
            return plate_text, characters

        except Exception as e:
            self.logger.error(f"Error in EasyOCR: {e}")
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