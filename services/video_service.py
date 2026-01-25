"""
Video service - License Plate Detection, Cropping, and OCR
"""
import os
import logging
from werkzeug.utils import secure_filename
from processors.video_processor import VideoProcessor
from detectors.parking_detector import ParkingDetector


class VideoService:
    """Service class for video processing operations focused on license plate detection"""
    
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.video_processor = VideoProcessor()
        self.parking_detector = self.video_processor.parking_detector  # Add reference to parking detector
        self.detected_plates = []
    
    def set_broadcast_functions(self, broadcast_parking_update, broadcast_detection, broadcast_plate_detection):
        """
        Set broadcast functions for real-time updates
        
        Args:
            broadcast_parking_update: Function to broadcast parking updates
            broadcast_detection: Function to broadcast detection updates
            broadcast_plate_detection: Function to broadcast plate detections
        """
        self.video_processor.set_broadcast_functions(
            broadcast_parking_update,
            broadcast_detection,
            broadcast_plate_detection
        )
    
    def is_allowed_file(self, filename):
        """
        Check if file extension is allowed
        
        Args:
            filename (str): Name of the file
            
        Returns:
            bool: True if file extension is allowed
        """
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS
    
    def validate_video_file(self, file):
        """
        Validate uploaded video file
        
        Args:
            file: FileStorage object from Flask request
            
        Returns:
            tuple: (success: bool, message: str, filename: str or None)
        """
        if not file:
            return False, "No file provided", None
        
        if file.filename == '':
            return False, "No file selected", None
        
        if not self.is_allowed_file(file.filename):
            return False, "Invalid file type. Allowed: MP4, AVI, MOV, MKV", None
        
        # Get secure filename
        filename = secure_filename(file.filename)
        
        return True, "File validation successful", filename
    
    def save_video_file(self, file, upload_folder):
        """
        Save uploaded video file to disk
        
        Args:
            file: FileStorage object from Flask request
            upload_folder (str): Path to upload folder
            
        Returns:
            tuple: (success: bool, message: str, filepath: str or None)
        """
        try:
            # Validate file first
            is_valid, message, filename = self.validate_video_file(file)
            if not is_valid:
                return False, message, None
            
            # Ensure upload folder exists
            os.makedirs(upload_folder, exist_ok=True)
            
            # Ensure detected plates folder exists
            plates_folder = os.path.join(upload_folder, 'detected_plates')
            os.makedirs(plates_folder, exist_ok=True)
            
            # Save file
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            
            self.logger.info(f"Video file saved: {filepath}")
            return True, "Video file saved successfully", filepath
            
        except Exception as e:
            self.logger.error(f"Error saving video file: {e}")
            return False, str(e), None
    
    def process_video_file(self, filepath, mode='parking'):
        """
        Start processing a video file
        
        Args:
            filepath (str): Path to video file
            mode (str): 'parking' for parking detection, 'plates' for license plate detection
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if not os.path.exists(filepath):
                return False, f"Video file not found: {filepath}"
            
            # Clear previous detections
            self.detected_plates = []
            
            # Start video processing in background with specified mode
            self.video_processor.process_video_file(filepath, mode=mode)
            
            mode_text = "parking space detection" if mode == 'parking' else "license plate detection"
            self.logger.info(f"Started processing video for {mode_text}: {filepath}")
            return True, f"Video processing started successfully ({mode_text})"
            
        except Exception as e:
            self.logger.error(f"Error starting video processing: {e}")
            return False, str(e)
    
    def is_processing(self):
        """
        Check if video processing is currently active
        
        Returns:
            bool: True if processing is active
        """
        return self.video_processor.is_processing
    
    def get_processing_status(self):
        """
        Get current video processing status
        
        Returns:
            dict: Dictionary containing processing status information
        """
        return {
            'is_processing': self.video_processor.is_processing,
            'plates_detected': len(self.detected_plates),
            'current_frame': getattr(self.video_processor, 'current_frame', 0)
        }
    
    def get_detected_plates(self):
        """
        Get list of detected license plates
        
        Returns:
            list: List of detected plate dictionaries
        """
        return self.detected_plates
    
    def add_detected_plate(self, plate_data):
        """
        Add a detected plate to the list
        
        Args:
            plate_data (dict): Plate detection data
        """
        self.detected_plates.append(plate_data)
        self.logger.info(f"Added detected plate: {plate_data.get('plate_number', 'Unknown')}")
    
    def export_detected_plates_csv(self):
        """
        Export detected plates to CSV format
        
        Returns:
            str: CSV formatted string
        """
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['plate_number', 'confidence', 'frame', 'timestamp'])
        
        writer.writeheader()
        for plate in self.detected_plates:
            writer.writerow({
                'plate_number': plate.get('plate_number', 'Unknown'),
                'confidence': plate.get('confidence', 0),
                'frame': plate.get('frame', 0),
                'timestamp': plate.get('timestamp', '')
            })
        
        return output.getvalue()