"""
Video service - handles all business logic for video processing
"""
import os
import logging
from werkzeug.utils import secure_filename
from video_processor import VideoProcessor


class VideoService:
    """Service class for video processing operations"""
    
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
    
    def __init__(self, app=None):
        self.logger = logging.getLogger(__name__)
        self.video_processor = VideoProcessor(app)
        self.app = app
    
    def set_app(self, app):
        """Set Flask app instance"""
        self.app = app
        self.video_processor.set_app(app)
    
    def set_broadcast_functions(self, broadcast_parking_update, broadcast_detection):
        """
        Set broadcast functions for real-time updates
        
        Args:
            broadcast_parking_update: Function to broadcast parking updates
            broadcast_detection: Function to broadcast detection updates
        """
        self.video_processor.set_broadcast_functions(
            broadcast_parking_update,
            broadcast_detection
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
            
            # Save file
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)
            
            self.logger.info(f"Video file saved: {filepath}")
            return True, "Video file saved successfully", filepath
            
        except Exception as e:
            self.logger.error(f"Error saving video file: {e}")
            return False, str(e), None
    
    def process_video_file(self, filepath):
        """
        Start processing a video file
        
        Args:
            filepath (str): Path to video file
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if not os.path.exists(filepath):
                return False, f"Video file not found: {filepath}"
            
            # Start video processing in background
            self.video_processor.process_video_file(filepath)
            
            self.logger.info(f"Started processing video: {filepath}")
            return True, "Video processing started successfully"
            
        except Exception as e:
            self.logger.error(f"Error starting video processing: {e}")
            return False, str(e)
    
    def start_live_feed(self, camera_index=0):
        """
        Start processing live video feed from camera
        
        Args:
            camera_index (int): Camera device index (default: 0)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if self.video_processor.is_processing:
                return False, "Video processing already in progress"
            
            self.video_processor.start_live_processing(camera_index)
            
            self.logger.info(f"Started live feed from camera {camera_index}")
            return True, f"Live feed started from camera {camera_index}"
            
        except Exception as e:
            self.logger.error(f"Error starting live feed: {e}")
            return False, str(e)
    
    def stop_live_feed(self):
        """
        Stop processing live video feed
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if not self.video_processor.is_processing:
                return False, "No live feed currently processing"
            
            self.video_processor.stop_live_processing()
            
            self.logger.info("Stopped live feed processing")
            return True, "Live feed processing stopped"
            
        except Exception as e:
            self.logger.error(f"Error stopping live feed: {e}")
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
            'vehicle_tracks': len(self.video_processor.vehicle_tracks) if hasattr(self.video_processor, 'vehicle_tracks') else 0
        }