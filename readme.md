# ParkSense - Smart Parking System Setup Guide

## Prerequisites

1. PostgreSQL database running
2. Python 3.8+ installed
3. All requirements installed: `pip install -r requirements.txt`

## Step-by-Step Setup

### 1. Database Initialization

```bash
# Create database
createdb parktrack

# Or using psql
psql -U postgres
CREATE DATABASE parktrack;
\q
```

### 2. Upload Parking Configuration Files

You need to copy your parking configuration files to `uploads/parking_config/`:

```bash
# Create the config directory
mkdir -p uploads/parking_config

# Copy your configuration files
cp path/to/your/src_points.json uploads/parking_config/
cp path/to/your/slots_points.json uploads/parking_config/
cp path/to/your/homography_matrix.npy uploads/parking_config/
```

**OR** use the setup script:

```bash
python setup_parking_config.py --source /path/to/your/config/folder
```

### 3. Run Database Migrations

```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

### 4. Start the Application

```bash
python main.py
```

The application will automatically:
- Create database tables
- Load parking configuration from `uploads/parking_config/`
- Initialize parking spaces in the database

### 5. Verify Setup

Navigate to `http://localhost:5000` and check:

1. **Configuration Status**: The dashboard should NOT show a warning about missing configuration
2. **Parking Spaces**: Statistics cards should show the correct number of total spaces
3. **Upload Button**: Should be enabled and green

## Usage

### Processing a Video

1. Go to Dashboard
2. Click "Upload & Process Video"
3. Select your parking lot video (MP4, AVI, MOV, MKV)
4. Click "Upload & Process Video"

The system will:
- Show live processing with real-time inference frames
- Display camera view (with bounding boxes) and schematic view (bird's-eye)
- Update parking statistics (occupied/available) in real-time
- Allow downloading the processed video when complete

### Expected Output

**Live View Shows:**
- **Camera View**: Original video with vehicle bounding boxes and parking slot overlays
- **Schematic View**: Bird's-eye view showing parking slots colored by occupancy
- **Statistics**: Real-time counts of occupied/available spaces
- **Progress Bar**: Processing progress percentage

**Final Output:**
- Processed video file saved as `{original_name}_parking_output.mp4`
- Download button appears when processing completes
- Database updated with all parking space states

## Configuration File Format

### slots_points.json
```json
[
  {
    "name": "Slot-1",
    "points": [
      [100, 200],
      [150, 200],
      [150, 250],
      [100, 250]
    ]
  },
  {
    "name": "Slot-2",
    "points": [
      [160, 200],
      [210, 200],
      [210, 250],
      [160, 250]
    ]
  }
]
```

### src_points.json
```json
[
  {
    "name": "parking_area",
    "points": [
      [x1, y1],
      [x2, y2],
      [x3, y3],
      [x4, y4]
    ]
  }
]
```

## Troubleshooting

### "Parking Detection Not Configured" Warning

**Cause**: Configuration files not found in `uploads/parking_config/`

**Fix**: 
1. Run `python setup_parking_config.py --source /path/to/config`
2. Or manually copy files to `uploads/parking_config/`
3. Restart the application

### "No parking spaces in database"

**Cause**: `slots_points.json` not found during initialization

**Fix**:
1. Ensure `uploads/parking_config/slots_points.json` exists
2. Restart application to trigger auto-initialization
3. Or manually run in Python:
```python
from app import app, db
from models import ParkingSpace
import json

with app.app_context():
    # Delete existing spaces
    ParkingSpace.query.delete()
    
    # Load and create from config
    with open('uploads/parking_config/slots_points.json') as f:
        slots = json.load(f)
    
    for i, slot in enumerate(slots):
        points = slot['points']
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        
        space = ParkingSpace(
            name=slot.get('name', f'Slot-{i+1}'),
            x1=int(min(xs)),
            y1=int(min(ys)),
            x2=int(max(xs)),
            y2=int(max(ys)),
            is_occupied=False
        )
        db.session.add(space)
    
    db.session.commit()
    print(f"Created {len(slots)} parking spaces")
```

### WebSocket Connection Issues

**Symptoms**: Live frames not updating

**Fix**:
1. Check browser console for WebSocket errors
2. Ensure Flask-SocketIO is installed: `pip install flask-socketio`
3. Check firewall settings
4. Try different browser

### Video Processing Stuck

**Cause**: YOLO model or OpenCV issues

**Fix**:
1. Check logs for detailed error messages
2. Verify YOLO model exists at `model/yolov8s.pt`
3. Ensure GPU/CUDA is properly configured (or use CPU mode)
4. Check video file format compatibility

## Performance Tips

1. **Frame Skip Rate**: Adjust `frame_skip` in `video_processor.py` line 138
   - Higher value = faster processing, less accurate
   - Lower value = slower processing, more accurate
   
2. **Streaming Rate**: Adjust `stream_every` in `video_processor.py` line 139
   - Higher value = less network traffic, less smooth live view
   - Lower value = more network traffic, smoother live view

3. **Image Quality**: Adjust JPEG quality in `_stream_parking_frames()` line 217
   - Higher value = better quality, more bandwidth
   - Lower value = lower quality, less bandwidth

## Architecture

```
Video Upload → VideoProcessor → ParkingDetector
                    ↓                    ↓
              WebSocket Broadcast ← Processed Frames
                    ↓                    ↓
              Dashboard (Live View) ← Database Update
```

## API Endpoints

- `POST /upload_video` - Upload video for parking detection
- `GET /api/parking_config_status` - Check configuration status
- `GET /api/parking_statistics` - Get current parking stats
- `GET /download_processed_video/<filename>` - Download processed video

## WebSocket Events

**Received by Client:**
- `parking_update` - Parking space state changed
- `new_detection` - Detection events (live frames, progress, completion)
- `plate_detected` - License plate detected (plates mode)

**Event Types in `new_detection`:**
- `live_frame` - Live camera and schematic frames
- `parking_stats_update` - Updated occupancy counts
- `processing_update` - Progress percentage
- `processing_complete` - Processing finished
- `error` - Processing error

## License

MIT License