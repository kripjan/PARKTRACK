"""
Parking Space Service - ROI Configuration Management
Handles ROI (Region of Interest) configuration for parking space visualization
"""
import os
import json
import logging
from datetime import datetime
try:
    import cv2
    import numpy as np
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False


class ParkingSpaceService:
    """Service class for ROI configuration management (renamed from parking space CRUD)"""
    
    def __init__(self, upload_folder='uploads'):
        self.logger = logging.getLogger(__name__)
        self.upload_folder = upload_folder
        self.config_file = os.path.join(upload_folder, 'roi_config.json')
        self.frame_file = os.path.join(upload_folder, 'cctv_frame.jpg')
        self.preview_file = os.path.join(upload_folder, 'roi_preview.jpg')
        
        # Ensure upload folder exists
        os.makedirs(upload_folder, exist_ok=True)
    
    def load_config(self):
        """
        Load ROI configuration from file
        
        Returns:
            list: List of ROI configurations or None if not found
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                self.logger.info(f"Loaded ROI configuration with {len(config)} entries")
                return config
            else:
                self.logger.warning("ROI configuration file not found")
                return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error loading ROI config: {e}")
            return None
    
    def save_config(self, config_data):
        """
        Save ROI configuration to file
        
        Args:
            config_data (list): List of ROI configurations
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Validate config structure
            if not isinstance(config_data, list):
                return False, "Configuration must be a list"
            
            # Save to file
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            self.logger.info(f"Saved ROI configuration with {len(config_data)} entries")
            return True, f"Configuration saved successfully ({len(config_data)} ROI entries)"
            
        except Exception as e:
            self.logger.error(f"Error saving ROI config: {e}")
            return False, str(e)
    
    def validate_config(self, config_data):
        """
        Validate ROI configuration structure and data
        
        Args:
            config_data (list): Configuration to validate
            
        Returns:
            tuple: (valid: bool, message: str)
        """
        try:
            if not isinstance(config_data, list):
                return False, "Configuration must be a JSON array"
            
            if len(config_data) == 0:
                return False, "Configuration cannot be empty"
            
            # Validate each ROI entry
            for idx, roi in enumerate(config_data):
                # Check if entry is a dictionary
                if not isinstance(roi, dict):
                    return False, f"ROI entry {idx} must be an object"
                
                # Check required fields
                required_fields = ['type', 'name', 'points']
                for field in required_fields:
                    if field not in roi:
                        return False, f"ROI entry {idx} missing required field: {field}"
                
                # Validate type
                valid_types = ['line', 'rectangle', 'polyline']
                if roi['type'] not in valid_types:
                    return False, f"Invalid type '{roi['type']}' in ROI entry {idx}. Must be one of: {', '.join(valid_types)}"
                
                # Validate points
                if not isinstance(roi['points'], list):
                    return False, f"Points in ROI entry {idx} must be a list"
                
                if len(roi['points']) < 2:
                    return False, f"ROI entry {idx} must have at least 2 points"
                
                # Validate point structure
                for point_idx, point in enumerate(roi['points']):
                    if not isinstance(point, list) or len(point) != 2:
                        return False, f"Point {point_idx} in ROI entry {idx} must be [x, y]"
                    
                    if not all(isinstance(coord, (int, float)) for coord in point):
                        return False, f"Coordinates in point {point_idx} of ROI entry {idx} must be numbers"
            
            return True, "Configuration is valid"
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def upload_config_file(self, file):
        """
        Process uploaded ROI configuration file
        
        Args:
            file: FileStorage object from Flask request
            
        Returns:
            tuple: (success: bool, message: str, config: list or None)
        """
        try:
            # Check file extension
            allowed_extensions = {'json', 'txt'}
            if not ('.' in file.filename and 
                    file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
                return False, "Invalid file type. Please upload JSON or TXT file", None
            
            # Read file content
            content = file.read().decode('utf-8')
            
            # Parse JSON
            try:
                config_data = json.loads(content)
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON format: {str(e)}", None
            
            # Validate configuration
            valid, message = self.validate_config(config_data)
            if not valid:
                return False, message, None
            
            # Save configuration
            success, save_message = self.save_config(config_data)
            if not success:
                return False, save_message, None
            
            return True, f"Configuration uploaded successfully ({len(config_data)} ROI entries)", config_data
            
        except Exception as e:
            self.logger.error(f"Error uploading config file: {e}")
            return False, str(e), None
    
    def upload_frame(self, file):
        """
        Process uploaded CCTV frame image
        
        Args:
            file: FileStorage object from Flask request
            
        Returns:
            tuple: (success: bool, message: str, filepath: str or None)
        """
        try:
            # Check file extension
            allowed_extensions = {'jpg', 'jpeg', 'png', 'bmp'}
            if not ('.' in file.filename and 
                    file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
                return False, "Invalid file type. Please upload JPG, PNG, or BMP", None
            
            # Save the file
            file.save(self.frame_file)
            
            # Verify it's a valid image
            if CV_AVAILABLE:
                img = cv2.imread(self.frame_file)
                if img is None:
                    os.remove(self.frame_file)
                    return False, "Invalid image file", None
                
                height, width = img.shape[:2]
                self.logger.info(f"Uploaded frame: {width}x{height}")
            
            return True, "Frame uploaded successfully", self.frame_file
            
        except Exception as e:
            self.logger.error(f"Error uploading frame: {e}")
            return False, str(e), None
    
    def generate_preview(self):
        """
        Generate preview image with ROI overlays drawn on CCTV frame
        
        Returns:
            tuple: (success: bool, message: str, preview_path: str or None)
        """
        try:
            # Check if OpenCV is available
            if not CV_AVAILABLE:
                return False, "OpenCV not available. Cannot generate preview", None
            
            # Check if config exists
            config = self.load_config()
            if not config:
                return False, "No ROI configuration found. Please upload configuration first", None
            
            # Check if frame exists
            if not os.path.exists(self.frame_file):
                return False, "No CCTV frame found. Please upload frame first", None
            
            # Read the frame
            frame = cv2.imread(self.frame_file)
            if frame is None:
                return False, "Failed to read frame image", None
            
            # Draw ROI regions
            roi_count = 0
            for roi in config:
                try:
                    roi_type = roi['type']
                    roi_name = roi['name']
                    points = roi['points']
                    
                    if roi_type == 'line':
                        # Draw line (yellow)
                        if len(points) >= 2:
                            pt1 = tuple(map(int, points[0]))
                            pt2 = tuple(map(int, points[1]))
                            cv2.line(frame, pt1, pt2, (0, 255, 255), 3)
                            # Add label
                            cv2.putText(frame, roi_name, pt1, 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                            roi_count += 1
                    
                    elif roi_type == 'rectangle':
                        # Draw rectangle (green)
                        if len(points) >= 4:
                            pts = np.array(points, np.int32)
                            pts = pts.reshape((-1, 1, 2))
                            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
                            # Add semi-transparent fill
                            overlay = frame.copy()
                            cv2.fillPoly(overlay, [pts], (0, 255, 0))
                            cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
                            # Add label
                            cv2.putText(frame, roi_name, tuple(map(int, points[0])), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            roi_count += 1
                    
                    elif roi_type == 'polyline':
                        # Draw polyline (magenta)
                        if len(points) >= 2:
                            pts = np.array(points, np.int32)
                            pts = pts.reshape((-1, 1, 2))
                            cv2.polylines(frame, [pts], True, (255, 0, 255), 2)
                            # Add semi-transparent fill
                            overlay = frame.copy()
                            cv2.fillPoly(overlay, [pts], (255, 0, 255))
                            cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
                            # Add label
                            cv2.putText(frame, roi_name, tuple(map(int, points[0])), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
                            roi_count += 1
                
                except Exception as e:
                    self.logger.warning(f"Error drawing ROI '{roi.get('name', 'unknown')}': {e}")
                    continue
            
            # Add info text at top
            info_text = f"ROI Configuration: {roi_count} regions"
            cv2.putText(frame, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Save preview
            cv2.imwrite(self.preview_file, frame)
            
            self.logger.info(f"Generated preview with {roi_count} ROI regions")
            return True, f"Preview generated successfully ({roi_count} regions)", self.preview_file
            
        except Exception as e:
            self.logger.error(f"Error generating preview: {e}")
            return False, str(e), None
    
    def get_config_summary(self):
        """
        Get summary of current ROI configuration
        
        Returns:
            dict: Summary information about current configuration
        """
        try:
            config = self.load_config()
            
            if not config:
                return {
                    'exists': False,
                    'total_rois': 0,
                    'by_type': {},
                    'frame_uploaded': os.path.exists(self.frame_file),
                    'preview_available': os.path.exists(self.preview_file)
                }
            
            # Count ROIs by type
            by_type = {}
            for roi in config:
                roi_type = roi.get('type', 'unknown')
                by_type[roi_type] = by_type.get(roi_type, 0) + 1
            
            return {
                'exists': True,
                'total_rois': len(config),
                'by_type': by_type,
                'rois': config,
                'frame_uploaded': os.path.exists(self.frame_file),
                'preview_available': os.path.exists(self.preview_file)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting config summary: {e}")
            return {
                'exists': False,
                'error': str(e)
            }
    
    def delete_config(self):
        """
        Delete ROI configuration and associated files
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            deleted_files = []
            
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
                deleted_files.append('configuration')
            
            if os.path.exists(self.frame_file):
                os.remove(self.frame_file)
                deleted_files.append('frame')
            
            if os.path.exists(self.preview_file):
                os.remove(self.preview_file)
                deleted_files.append('preview')
            
            if deleted_files:
                message = f"Deleted: {', '.join(deleted_files)}"
                self.logger.info(message)
                return True, message
            else:
                return True, "No files to delete"
                
        except Exception as e:
            self.logger.error(f"Error deleting config: {e}")
            return False, str(e)
    
    def export_config(self):
        """
        Export current configuration as formatted JSON string
        
        Returns:
            tuple: (success: bool, config_json: str or None, message: str)
        """
        try:
            config = self.load_config()
            if not config:
                return False, None, "No configuration to export"
            
            config_json = json.dumps(config, indent=2)
            return True, config_json, "Configuration exported successfully"
            
        except Exception as e:
            self.logger.error(f"Error exporting config: {e}")
            return False, None, str(e)