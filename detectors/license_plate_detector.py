"""
Unified License Plate Detector
Handles both image uploads and video frame processing
"""
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
      # Hardcoded class-index → label mapping for the Nepali OCR model.
    # This overrides whatever names are embedded in the .pt file, which
    # may be stale or incorrect (e.g. 'class_14' instead of 'BAA').
    OCR_CLASS_NAMES = {
        0:  'KA',
        1:  'KO',
        2:  'KHA',
        3:  'GA',
        4:  'CHA',
        5:  'JA',
        6:  'JHA',
        7:  'YNA',
        8:  'DI',
        9:  'TA',
        10: 'NA',
        11: 'PA',
        12: 'PRA',
        13: 'BA',
        14: 'BAA',
        15: 'BHE',
        16: 'MA',
        17: 'ME',
        18: 'YA',
        19: 'LU',
        20: 'C',
        21: 'SU',
        22: 'SE',
        23: 'HA',
        24: '0',
        25: '1',
        26: '2',
        27: '3',
        28: '4',
        29: '5',
        30: '6',
        31: '7',
        32: '8',
        33: '9',
        34: 'pradesh',
        35: 'bagmati',
        36: 'madhesh',
        37: 'karnali',
    }

    def __init__(self, upload_folder='uploads'):
        self.logger = logging.getLogger(__name__)
        self.upload_folder = upload_folder
        self.plates_folder = os.path.join(upload_folder, 'detected_plates')
        self.embossed_folder = os.path.join(self.plates_folder, 'embossed')
        self.nepali_folder = os.path.join(self.plates_folder, 'nepali')
        
        # Ensure folders exist
        os.makedirs(self.plates_folder, exist_ok=True)
        os.makedirs(self.embossed_folder, exist_ok=True)
        os.makedirs(self.nepali_folder, exist_ok=True)
        
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
            ocr_model_path = "model\\nepali_char_det_v3.pt"
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
                Shared processing pipeline:
          1. Detect plate bounding box
          2. Crop plate region
          3. Optionally save cropped plate
          4. Run OCR
          5. Return structured result

        
                Args:
            image (numpy.ndarray): Input image (full frame or vehicle ROI).
            save_cropped (bool): Whether to save the cropped plate.

        Returns:
            dict: Detection result (same schema as detect_from_image).
        """
        result = {
            'success':            False,
            'plate_text':         '',
            'confidence':         0.0,
            'cropped_plate_path': None,
            'bbox':               None,
            'characters':         [],
            'timestamp':          datetime.now().isoformat(),
            'message':            '',
        }
        # Check if models are loaded
        if not CV_AVAILABLE or self.plate_detector is None:
            result['message'] = "Plate detection model not available"
            return result
        
        # Step 1: locate plate
        plate_bbox, plate_confidence = self._detect_plate_bbox(image)
        
        if plate_bbox is None:
            result['message'] = "No license plate detected in image"
            return result
        
        # Step 2: Crop 
        cropped_plate = self._crop_plate(image, plate_bbox)
        
        if cropped_plate is None:
            result['message'] = "Failed to crop plate region"
            return result
        
        # Step 3: Save cropped plate (if requested)
        if save_cropped:
            result['cropped_plate_path'] = self._save_cropped_plate(cropped_plate, is_embossed=is_embossed)
        
        # Step 4: Perform OCR — branch based on plate type
        if is_embossed:
            plate_text, characters = self._perform_easyocr(cropped_plate)
        else:
            # This is the path that was working before!
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
            
            if not results or results[0].boxes is None or len(results[0].boxes) == 0:               
                return None, 0.0
            
            # Get highest confidence detection
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()
            
            best_idx   = int(np.argmax(confidences))
            bbox       = tuple(map(int, boxes[best_idx]))
            confidence = float(confidences[best_idx])
            
            return bbox, confidence
            
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
    
    def _save_cropped_plate(self, cropped_plate, is_embossed=False):
        """
        Save cropped plate to the appropriate subfolder based on plate type.
        
        Folder structure:
          detected_plates/
            embossed/   ← English raised character plates
            nepali/     ← Nepali/Devanagari script plates
        
        Returns:
            str: Path to saved file
        """
        try:
            target_folder = self.embossed_folder if is_embossed else self.nepali_folder
            plate_type = 'embossed' if is_embossed else 'nepali'
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = f'{plate_type}_{timestamp}.jpg'
            filepath = os.path.join(target_folder, filename)
            
            cv2.imwrite(filepath, cropped_plate)
            self.logger.info(f"Saved cropped plate [{plate_type}]: {filename}")
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error saving cropped plate: {e}")
            return None
    
    #===================================================
    # CHARACTER SORTING
    # ============================================================

    @staticmethod
    def _sort_characters(characters):
        """
        Sort detected characters into rows using median-gap thresholding.
        Works correctly for 1, 2, or any number of rows.

        Algorithm:
          1. Sort all characters top-to-bottom by top_y.
          2. Compute consecutive gaps between top_y values.
          3. A new row starts wherever a gap exceeds max(median_gap * 2, 5px).
          4. Within each row, sort left-to-right by centre x.

        Args:
            characters (list[dict]): Each dict must have 'top_y' and 'x' keys.

        Returns:
            tuple:
                rows        — list[list[dict]], one sub-list per row, left-to-right order.
                sorted_flat — flat list of all chars in reading order (top→bottom, left→right).
        """
        if not characters:
            return [], []

        if len(characters) == 1:
            return [[characters[0]]], [characters[0]]

        # Sort top-to-bottom
        characters.sort(key=lambda c: c['top_y'])

        top_ys        = [c['top_y'] for c in characters]
        gaps          = [top_ys[i + 1] - top_ys[i] for i in range(len(top_ys) - 1)]
        median_gap    = float(np.median(gaps))
        gap_threshold = max(median_gap * 2.0, 5.0)

        rows        = []
        current_row = [characters[0]]

        for i, char in enumerate(characters[1:]):
            if gaps[i] > gap_threshold:
                rows.append(current_row)
                current_row = [char]
            else:
                current_row.append(char)
        rows.append(current_row)

        # Sort each row left-to-right
        for row in rows:
            row.sort(key=lambda c: c['x'])

        sorted_flat = [c for row in rows for c in row]
        return rows, sorted_flat

    # ============================================================
    # OCR
    # ============================================================
    def _perform_ocr(self, cropped_plate):
        """
        Perform OCR on cropped plate using Nepali model with Debugging
        """
        if self.ocr_model is None:
            self.logger.error("DEBUG: OCR Model is None!")
            return '', []

        try:
            # 1. Image Info Debug
            h, w = cropped_plate.shape[:2]
            self.logger.info(f"DEBUG: OCR starting. Crop size: {w}x{h}")

            # 2. Run Inference
            results = self.ocr_model(cropped_plate, conf=0.2, iou=0.25,agnostic_nms=True, verbose=True) # Lowered conf for debug

            if not results or results[0].boxes is None or len(results[0].boxes) == 0:
                self.logger.warning("DEBUG: OCR Model detected ZERO boxes.")
                return '', []

            # Extract raw detections
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()
            classes = results[0].boxes.cls.cpu().numpy()
            
            self.logger.info(f"DEBUG: Raw detections found: {len(boxes)}")

            # --- VISUAL DEBUG: Draw every single raw detection ---
            debug_img = cropped_plate.copy()
            
            PROVINCE_CLASS_IDS = {34, 35, 36, 37}
            PROVINCE_CONF      = 0.1
            PROVINCE_MIN_RATIO = 2
            CHAR_CONF          = 0.25

            characters = []
            for i, (box, conf, cls) in enumerate(zip(boxes, confidences, classes)):
                x1, y1, x2, y2 = map(int, box)
                cls_id = int(cls)
                label = self.OCR_CLASS_NAMES.get(cls_id, f'?{cls_id}')
                bw, bh = (x2 - x1), (y2 - y1)
                ratio = bw / bh if bh > 0 else 0.0
                conf_f = float(conf)

                # Log every single hit to console
                self.logger.info(f"  [Det {i}] {label} | Conf: {conf_f:.2f} | Ratio: {ratio:.2f}")

                # Draw on debug image (Yellow = Raw, Green = Accepted, Red = Filtered Out)
                color = (0, 255, 255) # Default Yellow
                
                is_accepted = False
                MAX_CHAR_RATIO = 2.0  # Normal characters shouldn't be twice as wide as they are tall

                if cls_id in PROVINCE_CLASS_IDS:
                    # PROVINCE logic: Must be WIDE
                    if ratio >= PROVINCE_MIN_RATIO and conf_f >= PROVINCE_CONF:
                        is_accepted = True
                else:
                    # CHARACTER logic: Must NOT be too wide
                    if conf_f >= CHAR_CONF and ratio < MAX_CHAR_RATIO:
                        is_accepted = True
                    else:
                        # This will now catch that stretched JHA and turn it RED
                        self.logger.info(f"  [REJECTED] {label} - Ratio {ratio:.2f} too high for a char")

                cv2.rectangle(debug_img, (x1, y1), (x2, y2), color, 1)
                cv2.putText(debug_img, f"{label} {conf_f:.1f}", (x1, y1-5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)

                if is_accepted:
                    characters.append({
                        'char': label,
                        'confidence': conf_f,
                        'x': float((x1 + x2) / 2),
                        'top_y': float(y1),
                        'box': [float(x1), float(y1), float(x2), float(y2)],
                    })

            # Save the debug image to see what's happening
            debug_path = os.path.join(self.upload_folder, "last_ocr_debug.jpg")
            cv2.imwrite(debug_path, debug_img)
            self.logger.info(f"DEBUG: Saved visual check to {debug_path}")

            if not characters:
                self.logger.warning("DEBUG: All detections were filtered out by Ratio or Confidence!")
                return '', []

            # Sort and finish
            rows, sorted_flat = self._sort_characters(characters)
            plate_text = ''.join(c['char'] for c in sorted_flat)
            return plate_text, sorted_flat

        except Exception as e:
            self.logger.error(f"DEBUG: OCR Exception: {e}", exc_info=True)
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