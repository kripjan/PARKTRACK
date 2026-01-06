# Smart Parking System

## Overview

A comprehensive real-time parking management system that uses computer vision to detect vehicles, recognize license plates, and automate parking space monitoring. The system provides live video processing, vehicle tracking, automated toll calculation, and comprehensive analytics through a web-based dashboard with real-time updates via WebSocket connections.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Template Engine**: Flask with Jinja2 templates for server-side rendering
- **UI Framework**: Bootstrap 5 with dark theme for responsive design
- **Real-time Communication**: Socket.IO for live updates and video feed status
- **Interactive Components**: Canvas-based parking space management, real-time charts using Chart.js
- **File Upload**: Multi-format video upload with progress tracking

### Backend Architecture
- **Web Framework**: Flask application with modular route organization
- **Database ORM**: SQLAlchemy with declarative base for data modeling
- **Real-time Features**: Flask-SocketIO for WebSocket communication
- **Computer Vision Pipeline**: 
  - YOLO v8 for vehicle detection
  - Custom license plate recognition module
  - OpenCV for video processing and image manipulation
- **Modular Components**:
  - VideoProcessor: Handles live camera feeds and uploaded video analysis
  - ParkingManager: Manages vehicle entry/exit logic and toll calculation
  - LicensePlateDetector: Handles OCR and plate recognition

### Data Architecture
- **Core Models**:
  - Vehicle: License plate tracking with visit history
  - ParkingSpace: Configurable rectangular regions with coordinates
  - ParkingSession: Active/historical parking records with toll calculation
  - DetectionLog: Audit trail of all vehicle detections
  - SystemConfig: Application-wide configuration storage
- **Relationships**: Foreign key relationships between vehicles, spaces, and sessions
- **Session Management**: Active session tracking with automatic exit detection

### Processing Architecture
- **Multi-threading**: Separate threads for video processing to prevent UI blocking
- **Vehicle Tracking**: Custom tracking algorithm with coordinate-based vehicle identification
- **Toll Calculation**: Time-based pricing with configurable rates
- **Space Management**: Visual canvas-based parking space definition with coordinate mapping

## External Dependencies

### Computer Vision Libraries
- **Ultralytics YOLO**: Pre-trained vehicle detection models (yolov8s.pt)
- **OpenCV**: Video processing, image manipulation, and camera interface
- **NumPy**: Numerical operations for image processing

### Database
- **PostgreSQL**: Primary database for persistent storage (configurable via DATABASE_URL)
- **SQLAlchemy**: ORM with connection pooling and automatic reconnection

### Web Technologies
- **Flask Extensions**: SQLAlchemy, SocketIO for enhanced functionality
- **Bootstrap 5**: UI framework with dark theme support
- **Chart.js**: Real-time data visualization for analytics dashboard
- **Socket.IO**: Bidirectional real-time communication

### Infrastructure
- **File Storage**: Local file system for video uploads (configurable upload directory)
- **Session Management**: Flask sessions with configurable secret key
- **Proxy Support**: ProxyFix middleware for deployment behind reverse proxies
- **Logging**: Python logging framework with configurable levels

### Development Tools
- **Werkzeug**: WSGI utilities and development server
- **Bootstrap Icons**: Icon library for UI elements