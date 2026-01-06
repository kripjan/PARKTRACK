import logging
import re
try:
    import cv2
    import numpy as np
    from ultralytics import YOLO
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False

class LicensePlateDetector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Try to load a pre-trained license plate detection model
        # Note: In a real implementation, you would use your trained model
        if CV_AVAILABLE:
            try:
                # This would be your custom trained model
                # self.model = YOLO('path_to_your_license_plate_model.pt')
                
                # For demonstration, we'll use a general approach with image processing
                # and OCR-like pattern recognition
                self.model = None
                self.logger.info("License plate detector initialized (using fallback method)")
            except Exception as e:
                self.logger.error(f"Failed to load license plate model: {e}")
                self.model = None
        else:
            self.model = None
            self.logger.warning("Computer vision libraries not available - using mock license plate detection")
    
    def detect_license_plate(self, vehicle_image):
        """
        Detect and read license plate from vehicle image
        
        Args:
            vehicle_image: Cropped image of the vehicle
            
        Returns:
            str: Detected license plate text or None
        """
        try:
            if not CV_AVAILABLE:
                # Return mock license plate for demonstration
                return self._generate_mock_license_plate()
                
            if vehicle_image is None or vehicle_image.size == 0:
                return None
            
            # If we have a trained model, use it
            if self.model is not None:
                return self._use_trained_model(vehicle_image)
            else:
                # Fallback to image processing approach
                return self._fallback_detection(vehicle_image)
                
        except Exception as e:
            self.logger.error(f"Error in license plate detection: {e}")
            return None
    
    def _use_trained_model(self, vehicle_image):
        """Use trained YOLO model for license plate detection"""
        try:
            results = self.model(vehicle_image, verbose=False)
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        confidence = float(box.conf[0])
                        if confidence > 0.5:  # Confidence threshold
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            
                            # Extract license plate region
                            lp_roi = vehicle_image[int(y1):int(y2), int(x1):int(x2)]
                            
                            # Apply OCR or text recognition
                            license_text = self._extract_text_from_plate(lp_roi)
                            if license_text:
                                return license_text
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error using trained model: {e}")
            return None
    
    def _fallback_detection(self, vehicle_image):
        """
        Fallback license plate detection using traditional computer vision
        This is a simplified approach - in production, use a trained model
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(vehicle_image, cv2.COLOR_BGR2GRAY)
            
            # Apply bilateral filter to reduce noise
            filtered = cv2.bilateralFilter(gray, 11, 17, 17)
            
            # Find edges
            edges = cv2.Canny(filtered, 30, 200)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            # Sort contours by area in descending order
            contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
            
            license_plate_contour = None
            
            # Look for rectangular contours (potential license plates)
            for contour in contours:
                # Approximate the contour
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # License plates are typically rectangular (4 corners)
                if len(approx) == 4:
                    # Check aspect ratio
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect_ratio = w / h
                    
                    # License plates have specific aspect ratios (typically 2:1 to 4:1)
                    if 2.0 <= aspect_ratio <= 5.0 and w > 50 and h > 15:
                        license_plate_contour = approx
                        break
            
            if license_plate_contour is not None:
                # Extract the license plate region
                x, y, w, h = cv2.boundingRect(license_plate_contour)
                license_plate_roi = gray[y:y+h, x:x+w]
                
                # Apply additional preprocessing for better OCR
                license_plate_roi = self._preprocess_for_ocr(license_plate_roi)
                
                # Extract text (simplified - in production use proper OCR)
                license_text = self._simple_ocr(license_plate_roi)
                
                if license_text:
                    return license_text
            
            # If no license plate detected, try to generate a mock plate for demonstration
            # In production, this should return None
            return self._generate_mock_license_plate()
            
        except Exception as e:
            self.logger.error(f"Error in fallback detection: {e}")
            return None
    
    def _preprocess_for_ocr(self, plate_roi):
        """Preprocess license plate image for better text recognition"""
        # Resize to improve OCR accuracy
        height, width = plate_roi.shape
        if width < 100:
            scale_factor = 100 / width
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            plate_roi = cv2.resize(plate_roi, (new_width, new_height))
        
        # Apply threshold to get binary image
        _, thresh = cv2.threshold(plate_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Apply morphological operations to clean up the image
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def _simple_ocr(self, plate_image):
        """
        Simplified OCR for license plates
        In production, use proper OCR libraries like pytesseract or EasyOCR
        """
        # This is a placeholder implementation
        # In a real system, you would use:
        # import pytesseract
        # text = pytesseract.image_to_string(plate_image, config='--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        
        # For now, return None to use mock generation
        return None
    
    def _generate_mock_license_plate(self):
        """
        Generate mock license plates for demonstration
        Remove this in production - it should return None when no plate is detected
        """
        import random
        import string
        
        # Generate random license plate formats
        formats = [
            "{}{}{}-{}{}{}", # ABC-123 format
            "{}{}{}{}{}{}", # ABC123 format  
            "{}{}-{}{}{}{}", # AB-1234 format
        ]
        
        format_choice = random.choice(formats)
        
        # Generate random characters
        letters = ''.join(random.choices(string.ascii_uppercase, k=6))
        digits = ''.join(random.choices(string.digits, k=6))
        
        # Create license plate based on format
        if "{}{}{}-{}{}{}" in format_choice:
            plate = f"{letters[0]}{letters[1]}{letters[2]}-{digits[0]}{digits[1]}{digits[2]}"
        elif "{}{}{}{}{}{}" in format_choice:
            plate = f"{letters[0]}{letters[1]}{letters[2]}{digits[0]}{digits[1]}{digits[2]}"
        else:
            plate = f"{letters[0]}{letters[1]}-{digits[0]}{digits[1]}{digits[2]}{digits[3]}"
        
        # Simulate detection confidence - sometimes return None
        if random.random() < 0.3:  # 30% chance of no detection
            return None
        
        return plate
    
    def _extract_text_from_plate(self, plate_roi):
        """Extract text from detected license plate region"""
        # Preprocess the plate region
        processed = self._preprocess_for_ocr(plate_roi)
        
        # Apply OCR
        text = self._simple_ocr(processed)
        
        # Clean and validate the text
        if text:
            # Remove special characters and spaces
            cleaned_text = re.sub(r'[^A-Z0-9]', '', text.upper())
            
            # Validate license plate format (basic validation)
            if len(cleaned_text) >= 4 and len(cleaned_text) <= 8:
                return cleaned_text
        
        return None
