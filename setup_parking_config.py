"""
Helper script to set up parking configuration files
Run this once to create the parking configuration from your existing files
"""
import os
import shutil
import json
import numpy as np
import cv2

# Source paths (your existing files)
SOURCE_FILES = {
    'src_points': r'C:\Users\HP\Desktop\major\slot\src_points.json',
    'slots_points': r'C:\Users\HP\Desktop\major\slot\slots_points.json',
    'homography_matrix': r'C:\Users\HP\Desktop\major\slot\homography_matrix.npy',
}

# Destination folder
DEST_FOLDER = 'uploads/parking_config'

def setup_parking_config():
    """Copy parking configuration files to the application folder"""
    
    print("Setting up parking configuration...")
    
    # Create destination folder
    os.makedirs(DEST_FOLDER, exist_ok=True)
    print(f"Created folder: {DEST_FOLDER}")
    
    # Copy source points
    if os.path.exists(SOURCE_FILES['src_points']):
        shutil.copy(SOURCE_FILES['src_points'], 
                   os.path.join(DEST_FOLDER, 'src_points.json'))
        print("✓ Copied src_points.json")
    else:
        print("✗ src_points.json not found")
    
    # Copy slots points
    if os.path.exists(SOURCE_FILES['slots_points']):
        shutil.copy(SOURCE_FILES['slots_points'], 
                   os.path.join(DEST_FOLDER, 'slots_points.json'))
        print("✓ Copied slots_points.json")
    else:
        print("✗ slots_points.json not found")
    
    # Copy homography matrix
    if os.path.exists(SOURCE_FILES['homography_matrix']):
        H = np.load(SOURCE_FILES['homography_matrix'])
        np.save(os.path.join(DEST_FOLDER, 'homography_matrix.npy'), H)
        print("✓ Copied homography_matrix.npy")
        
        # Create inverse homography
        H_inv = np.linalg.inv(H)
        np.save(os.path.join(DEST_FOLDER, 'homography_inv.npy'), H_inv)
        print("✓ Created homography_inv.npy")
    else:
        print("✗ homography_matrix.npy not found")
    
    # Generate camera_slots.npy from slots_points.json and inverse homography
    generate_camera_slots()
    
    print("\n✓ Parking configuration setup complete!")
    print(f"Configuration files are in: {DEST_FOLDER}")

def generate_camera_slots():
    """Generate camera view slots from schematic slots using inverse homography"""
    
    slots_path = os.path.join(DEST_FOLDER, 'slots_points.json')
    h_inv_path = os.path.join(DEST_FOLDER, 'homography_inv.npy')
    
    if not os.path.exists(slots_path) or not os.path.exists(h_inv_path):
        print("✗ Cannot generate camera_slots.npy - missing required files")
        return
    
    # Load schematic slots
    with open(slots_path, 'r') as f:
        schematic_slots = json.load(f)
    
    # Load inverse homography
    H_inv = np.load(h_inv_path)
    
    # Transform each slot to camera view
    camera_slots = []
    
    for slot in schematic_slots:
        points = np.float32(slot['points'])
        
        # Transform points using inverse homography
        transformed = cv2.perspectiveTransform(points.reshape(-1, 1, 2), H_inv)
        camera_slots.append(transformed.reshape(-1, 2))
    
    # Save camera slots
    camera_slots_array = np.array(camera_slots, dtype=object)
    np.save(os.path.join(DEST_FOLDER, 'camera_slots.npy'), camera_slots_array)
    print("✓ Generated camera_slots.npy")

if __name__ == '__main__':
    setup_parking_config()