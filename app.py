import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_migrate import Migrate

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
migrate=Migrate()
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
migrate.init_app(app,db)
# Initialize SocketIO with less strict configuration for development
socketio.init_app(app, cors_allowed_origins="*", async_mode='threading')

with app.app_context():
    # Import models to ensure tables are created
    from models import Vehicle, ParkingSession, ParkingSpace, DetectionLog, SystemConfig
    
# Import routes
import routes
