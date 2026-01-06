import os
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

# Create Flask app FIRST
app = Flask(__name__)
app.secret_key = "dev-secret"
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure app
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///parking.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Import db AFTER app creation
from models import db

# Register app with db
db.init_app(app)

# Import models AFTER init_app
from models import Vehicle, ParkingSpace, ParkingSession, DetectionLog, SystemConfig

# Create tables inside app context
with app.app_context():
    db.create_all()

# Routes
# @app.route("/")
# def dashboard():
#     return render_template("dashboard.html")

@app.route("/")
def video_upload():
    return render_template("video_upload.html")

# Run app
if __name__ == "__main__":
    app.run(debug=True)
