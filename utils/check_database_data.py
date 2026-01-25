"""
Script to check current database data
This will help diagnose why reports show 0 values

Usage: python check_database_data.py
"""
from datetime import datetime, timedelta
from app import app, db
from models import Vehicle, ParkingSpace, ParkingSession, DetectionLog
from sqlalchemy import func

def check_database():
    """Check and display current database statistics"""
    
    with app.app_context():
        print("\n" + "="*60)
        print("DATABASE STATUS CHECK")
        print("="*60)
        
        # Vehicles
        total_vehicles = Vehicle.query.count()
        print(f"\n📊 VEHICLES:")
        print(f"   Total Vehicles: {total_vehicles}")
        
        if total_vehicles > 0:
            recent_vehicles = Vehicle.query.order_by(Vehicle.last_seen.desc()).limit(5).all()
            print(f"   Recent vehicles:")
            for v in recent_vehicles:
                print(f"     - {v.license_plate} (visits: {v.total_visits})")
        
        # Parking Spaces
        total_spaces = ParkingSpace.query.count()
        occupied_spaces = ParkingSpace.query.filter_by(is_occupied=True).count()
        print(f"\n🅿️  PARKING SPACES:")
        print(f"   Total Spaces: {total_spaces}")
        print(f"   Occupied: {occupied_spaces}")
        print(f"   Available: {total_spaces - occupied_spaces}")
        
        # Parking Sessions
        total_sessions = ParkingSession.query.count()
        active_sessions = ParkingSession.query.filter_by(is_active=True).count()
        completed_sessions = ParkingSession.query.filter_by(is_active=False).count()
        
        print(f"\n🎫 PARKING SESSIONS:")
        print(f"   Total Sessions: {total_sessions}")
        print(f"   Active: {active_sessions}")
        print(f"   Completed: {completed_sessions}")
        
        # Revenue Analysis
        total_revenue = db.session.query(
            func.sum(ParkingSession.toll_amount)
        ).filter(ParkingSession.is_active == False).scalar()
        
        today = datetime.utcnow().date()
        today_revenue = db.session.query(
            func.sum(ParkingSession.toll_amount)
        ).filter(
            func.date(ParkingSession.exit_time) == today,
            ParkingSession.is_active == False
        ).scalar()
        
        # Last 7 days revenue
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        week_revenue = db.session.query(
            func.sum(ParkingSession.toll_amount)
        ).filter(
            ParkingSession.exit_time >= seven_days_ago,
            ParkingSession.is_active == False
        ).scalar()
        
        print(f"\n💰 REVENUE:")
        print(f"   Total All-Time: Rs. {total_revenue if total_revenue else 0:.2f}")
        print(f"   Last 7 Days: Rs. {week_revenue if week_revenue else 0:.2f}")
        print(f"   Today: Rs. {today_revenue if today_revenue else 0:.2f}")
        
        if completed_sessions > 0:
            avg_per_session = (total_revenue or 0) / completed_sessions
            print(f"   Avg per Session: Rs. {avg_per_session:.2f}")
        
        # Detection Logs
        total_detections = DetectionLog.query.count()
        entry_detections = DetectionLog.query.filter_by(detection_type='entry').count()
        exit_detections = DetectionLog.query.filter_by(detection_type='exit').count()
        plate_detections = DetectionLog.query.filter_by(detection_type='license_plate').count()
        
        print(f"\n🔍 DETECTIONS:")
        print(f"   Total Detections: {total_detections}")
        print(f"   Entries: {entry_detections}")
        print(f"   Exits: {exit_detections}")
        print(f"   License Plates: {plate_detections}")
        
        # Recent completed sessions with revenue
        recent_completed = ParkingSession.query.filter_by(
            is_active=False
        ).order_by(ParkingSession.exit_time.desc()).limit(5).all()
        
        if recent_completed:
            print(f"\n📝 RECENT COMPLETED SESSIONS:")
            for session in recent_completed:
                print(f"   - {session.vehicle.license_plate}: "
                      f"{session.duration_minutes}min, "
                      f"Rs. {session.toll_amount:.2f} "
                      f"(Exit: {session.exit_time.strftime('%Y-%m-%d %H:%M')})")
        
        # Daily revenue breakdown (last 7 days)
        daily_revenue = db.session.query(
            func.date(ParkingSession.exit_time).label('date'),
            func.sum(ParkingSession.toll_amount).label('revenue'),
            func.count(ParkingSession.id).label('sessions')
        ).filter(
            ParkingSession.exit_time >= seven_days_ago,
            ParkingSession.is_active == False
        ).group_by(func.date(ParkingSession.exit_time)).all()
        
        if daily_revenue:
            print(f"\n📅 DAILY REVENUE (Last 7 days):")
            for row in daily_revenue:
                print(f"   {row.date}: Rs. {row.revenue:.2f} ({row.sessions} sessions)")
        
        # Diagnosis
        print("\n" + "="*60)
        print("DIAGNOSIS:")
        print("="*60)
        
        issues = []
        if total_vehicles == 0:
            issues.append("❌ No vehicles in database")
        if total_spaces == 0:
            issues.append("❌ No parking spaces configured")
        if completed_sessions == 0:
            issues.append("❌ No completed parking sessions (all revenue will be Rs. 0.00)")
        if total_revenue == 0 or total_revenue is None:
            issues.append("❌ No revenue data (sessions may not have toll_amount set)")
        
        if issues:
            print("\nIssues found:")
            for issue in issues:
                print(f"  {issue}")
            print("\n💡 SOLUTION:")
            print("   Run: python populate_test_data.py")
            print("   This will create sample data for testing the reports page")
        else:
            print("\n✅ Database looks good!")
            print("   Reports page should display data correctly")
        
        print("="*60 + "\n")

if __name__ == '__main__':
    check_database()