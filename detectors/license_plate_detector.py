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


class LicensePlateDetector:
    """
    Unified license plate detector with Nepali OCR support.
    Works with both uploaded images and video frame ROIs.
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

        # Ensure folders exist
        os.makedirs(self.plates_folder, exist_ok=True)

        # Initialize models
        self.plate_detector = None
        self.ocr_model = None

        if CV_AVAILABLE:
            self._load_models()
        else:
            self.logger.warning("Computer vision libraries not available")

    # ============================================================
    # MODEL LOADING
    # ============================================================

    def _load_models(self):
        """Load YOLO models once during initialization."""
        try:
            plate_model_path = 'model/license_plate.pt'
            if os.path.exists(plate_model_path):
                self.plate_detector = YOLO(plate_model_path)
                self.logger.info("✔ License plate detection model loaded")
            else:
                self.logger.error(f"✘ Plate model not found: {plate_model_path}")

            ocr_model_path = 'model/new_nepali_char.pt'
            if os.path.exists(ocr_model_path):
                self.ocr_model = YOLO(ocr_model_path)
                self.logger.info("✔ Nepali OCR model loaded")
            else:
                self.logger.error(f"✘ OCR model not found: {ocr_model_path}")

        except Exception as e:
            self.logger.error(f"Error loading models: {e}")

    # ============================================================
    # PUBLIC API
    # ============================================================

    def detect_from_image(self, image_path, save_cropped=True):
        """
        Detect license plate from an uploaded image file.

        Args:
            image_path (str): Path to uploaded image.
            save_cropped (bool): Whether to save the cropped plate to disk.

        Returns:
            dict: {
                'success':            bool,
                'plate_text':         str,
                'confidence':         float,
                'cropped_plate_path': str or None,
                'bbox':               tuple or None,
                'characters':         list,
                'timestamp':          str,
                'message':            str,
            }
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                return self._error_result("Failed to read image file")
            return self._process(image, save_cropped=save_cropped)
        except Exception as e:
            self.logger.error(f"Error in detect_from_image: {e}")
            return self._error_result(str(e))

    def detect_from_roi(self, vehicle_roi):
        """
        Detect license plate from a video frame ROI.

        Args:
            vehicle_roi (numpy.ndarray): Cropped vehicle region from a video frame.

        Returns:
            str or None: Detected plate text, or None on failure.
        """
        try:
            if vehicle_roi is None or vehicle_roi.size == 0:
                return None
            result = self._process(vehicle_roi, save_cropped=False)
            return result['plate_text'] if result['success'] else None
        except Exception as e:
            self.logger.error(f"Error in detect_from_roi: {e}")
            return None

    # ============================================================
    # CORE PROCESSING PIPELINE
    # ============================================================

    def _process(self, image, save_cropped=True):
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

        if not CV_AVAILABLE or self.plate_detector is None:
            result['message'] = "Plate detection model not available"
            return result

        # Step 1 — locate plate
        plate_bbox, plate_confidence = self._detect_plate_bbox(image)
        if plate_bbox is None:
            result['message'] = "No license plate detected in image"
            return result

        # Step 2 — crop
        cropped_plate = self._crop_plate(image, plate_bbox)
        if cropped_plate is None:
            result['message'] = "Failed to crop plate region"
            return result

        # Step 3 — save (optional)
        if save_cropped:
            result['cropped_plate_path'] = self._save_cropped_plate(cropped_plate)

        # Step 4 — OCR
        plate_text, characters = self._perform_ocr(cropped_plate)

        # Step 5 — build result
        result.update({
            'success':    True,
            'plate_text': plate_text,
            'confidence': plate_confidence,
            'bbox':       plate_bbox,
            'characters': characters,
            'message':    (
                f"Successfully detected: {plate_text}"
                if plate_text
                else "Plate detected but OCR returned no text"
            ),
        })
        return result

    # ============================================================
    # INTERNAL PROCESSING STEPS
    # ============================================================

    def _detect_plate_bbox(self, image):
        """
        Run the plate-detection model and return the highest-confidence bbox.

        Returns:
            tuple: ((x1, y1, x2, y2), confidence) or (None, 0.0)
        """
        try:
            results = self.plate_detector(image, conf=0.13, verbose=False)

            if not results or results[0].boxes is None or len(results[0].boxes) == 0:
                return None, 0.0

            boxes       = results[0].boxes.xyxy.cpu().numpy()
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
        Crop the plate region from the image with optional padding.

        Args:
            image:   Source image.
            bbox:    (x1, y1, x2, y2) bounding box.
            padding: Extra pixels added on each side.

        Returns:
            numpy.ndarray or None
        """
        try:
            x1, y1, x2, y2 = bbox
            h, w = image.shape[:2]

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
        Save a cropped plate image to disk.

        Returns:
            str or None: Absolute path to the saved file.
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename  = f'plate_{timestamp}.jpg'
            filepath  = os.path.join(self.plates_folder, filename)
            cv2.imwrite(filepath, cropped_plate)
            self.logger.info(f"Saved cropped plate: {filename}")
            return filepath
        except Exception as e:
            self.logger.error(f"Error saving cropped plate: {e}")
            return None

    # ============================================================
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
        Run the Nepali OCR model on a cropped plate image,
        then sort the detected characters into reading order.

        Returns:
            tuple: (plate_text: str, characters: list[dict])
        """
        if self.ocr_model is None:
            return '', []

        try:
            results = self.ocr_model(cropped_plate, conf=0.35, verbose=False)

            if not results or results[0].boxes is None or len(results[0].boxes) == 0:
                return '', []

            boxes       = results[0].boxes.xyxy.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()
            classes     = results[0].boxes.cls.cpu().numpy()

            # Build character list
            characters = []
            for box, conf, cls in zip(boxes, confidences, classes):
                x1, y1, x2, y2 = box
                cls_id = int(cls)
                label  = self.OCR_CLASS_NAMES.get(cls_id, f'?{cls_id}')
                characters.append({
                    'char':       label,
                    'confidence': float(conf),
                    'x':          float((x1 + x2) / 2),
                    'top_y':      float(y1),
                    'box':        [float(x1), float(y1), float(x2), float(y2)],
                })

            if not characters:
                return '', []

            # Sort into rows using median-gap thresholding
            rows, sorted_flat = self._sort_characters(characters)

            plate_text = ''.join(c['char'] for c in sorted_flat)
            self.logger.info(f"OCR result: '{plate_text}'  ({len(rows)} row(s), {len(characters)} char(s))")
            return plate_text, sorted_flat

        except Exception as e:
            self.logger.error(f"Error performing OCR: {e}")
            return '', []

    # ============================================================
    # UTILITY
    # ============================================================

    def _error_result(self, message):
        """Return a failed-detection result dict with a descriptive message."""
        return {
            'success':            False,
            'plate_text':         '',
            'confidence':         0.0,
            'cropped_plate_path': None,
            'bbox':               None,
            'characters':         [],
            'timestamp':          datetime.now().isoformat(),
            'message':            message,
        }

    def is_available(self):
        """Return True if both models are loaded and ready."""
        return CV_AVAILABLE and self.plate_detector is not None and self.ocr_model is not None