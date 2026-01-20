import os
import json
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_migrate import Migrate

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate = Migrate()
socketio = SocketIO()

# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql+psycopg2://parktrack:parktrack@localhost/parktrack")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max file size

# Ensure upload directory exists
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# initialize extensions
db.init_app(app)
migrate.init_app(app, db)
# Initialize SocketIO with less strict configuration for development
socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')

# Import routes BEFORE creating tables to register them
import routes

def initialize_parking_spaces():
    """Initialize parking spaces from configuration file"""
    from models import ParkingSpace
    
    try:
        # Check if parking spaces already exist
        if ParkingSpace.query.count() > 0:
            logger.info(f"Parking spaces already initialized ({ParkingSpace.query.count()} spaces)")
            return True
        
        # Path to parking configuration
        slots_path = os.path.join(app.config['UPLOAD_FOLDER'], 'parking_config', 'slots_points.json')
        
        if not os.path.exists(slots_path):
            logger.warning(f"Parking configuration not found at: {slots_path}")
            logger.warning("Run setup_parking_config.py or upload configuration files")
            return False
        
        # Load slots configuration
        with open(slots_path, 'r') as f:
            slots_data = json.load(f)
        
        logger.info(f"Found {len(slots_data)} parking slots in configuration")
        
        # Create parking space records
        for i, slot in enumerate(slots_data):
            points = slot['points']
            
            # Calculate bounding box from polygon points
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            
            # Get slot name from config or generate default
            slot_name = slot.get('name', f'Slot-{i+1}')
            
            space = ParkingSpace(
                name=slot_name,
                x1=int(min(xs)),
                y1=int(min(ys)),
                x2=int(max(xs)),
                y2=int(max(ys)),
                is_occupied=False
            )
            db.session.add(space)
            logger.info(f"Created parking space: {slot_name}")
        
        db.session.commit()
        logger.info(f"✓ Successfully initialized {len(slots_data)} parking spaces")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing parking spaces: {e}")
        db.session.rollback()
        return False

with app.app_context():
    # Import models to ensure tables are created
    from models import Vehicle, ParkingSession, ParkingSpace, DetectionLog, SystemConfig
    
    # Create all tables
    db.create_all()
    logger.info("✓ Database tables created")
    
    # Initialize parking spaces from configuration
    initialize_parking_spaces()