"""
Report service - handles all business logic for reports and analytics
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from app import db
from models import Vehicle, ParkingSession, DetectionLog


class ReportService:
    """Service class for report and analytics operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_daily_revenue(self, days=7):
        """
        Get daily revenue for the specified number of days
        Fills in missing days with Rs. 0.00 to show complete timeline
        
        Args:
            days (int): Number of days to look back (default: 7)
            
        Returns:
            list: List of dictionaries with 'date' and 'revenue' keys for ALL days
        """
        try:
            from datetime import datetime, timedelta
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days-1)  # Include today
            
            # Query database for days with revenue
            results = db.session.query(
                func.date(ParkingSession.exit_time).label('date'),
                func.sum(ParkingSession.toll_amount).label('revenue')
            ).filter(
                ParkingSession.exit_time.between(start_date, end_date),
                ParkingSession.is_active == False
            ).group_by(func.date(ParkingSession.exit_time)).all()
            
            # Convert results to dictionary for easy lookup
            revenue_by_date = {}
            for row in results:
                revenue_by_date[row.date] = float(row.revenue) if row.revenue else 0.0
            
            # Generate complete list of all days in range
            daily_revenue = []
            current_date = start_date.date()
            end = end_date.date()
            
            while current_date <= end:
                daily_revenue.append({
                    'date': current_date,
                    'revenue': revenue_by_date.get(current_date, 0.0)  # Use 0.0 if no data
                })
                current_date += timedelta(days=1)
            
            return daily_revenue
            
        except Exception as e:
            self.logger.error(f"Error fetching daily revenue: {e}")
            return []
    
    def get_hourly_occupancy(self, date=None):
        """
        Get hourly occupancy data for a specific date
        Counts license plate detections as entries
        
        Args:
            date (datetime.date, optional): Date to get occupancy for (default: today)
            
        Returns:
            list: List of dictionaries with 'hour' and 'count' keys
        """
        try:
            if date is None:
                date = datetime.now().date()
            
            # Count license_plate detections (from Plate Corrector)
            # OR entry detections (from video processing)
            results = db.session.query(
                func.extract('hour', DetectionLog.timestamp).label('hour'),
                func.count(DetectionLog.id).label('count')
            ).filter(
                func.date(DetectionLog.timestamp) == date,
                DetectionLog.detection_type.in_(['license_plate', 'entry'])  # Count both types
            ).group_by(func.extract('hour', DetectionLog.timestamp)).all()
            
            # Convert to list of dictionaries for easier template access
            hourly_occupancy = []
            for row in results:
                hourly_occupancy.append({
                    'hour': int(row.hour) if row.hour else 0,
                    'count': int(row.count) if row.count else 0
                })
            
            return hourly_occupancy
            
        except Exception as e:
            self.logger.error(f"Error fetching hourly occupancy: {e}")
            return []
    
    def get_top_vehicles(self, limit=10):
        """
        Get top vehicles by visit frequency
        
        Args:
            limit (int): Maximum number of vehicles to return
            
        Returns:
            list: List of dictionaries with vehicle information
        """
        try:
            results = db.session.query(
                Vehicle.license_plate,
                Vehicle.total_visits,
                func.sum(ParkingSession.toll_amount).label('total_paid')
            ).join(ParkingSession).filter(
                ParkingSession.is_active == False
            ).group_by(Vehicle.id).order_by(desc(Vehicle.total_visits)).limit(limit).all()
            
            # Convert to list of dictionaries for easier template access
            top_vehicles = []
            for row in results:
                top_vehicles.append({
                    'license_plate': row.license_plate,
                    'total_visits': row.total_visits,
                    'total_paid': float(row.total_paid) if row.total_paid else 0.0
                })
            
            return top_vehicles
            
        except Exception as e:
            self.logger.error(f"Error fetching top vehicles: {e}")
            return []
    
    def get_total_revenue(self, start_date=None, end_date=None):
        """
        Get total revenue for a date range
        
        Args:
            start_date (datetime, optional): Start date for range
            end_date (datetime, optional): End date for range
            
        Returns:
            float: Total revenue
        """
        try:
            query = db.session.query(func.sum(ParkingSession.toll_amount)).filter(
                ParkingSession.is_active == False
            )
            
            if start_date:
                query = query.filter(ParkingSession.exit_time >= start_date)
            
            if end_date:
                query = query.filter(ParkingSession.exit_time <= end_date)
            
            revenue = query.scalar()
            return revenue or 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating total revenue: {e}")
            return 0.0
    
    def get_average_session_duration(self):
        """
        Calculate average parking session duration
        
        Returns:
            float: Average duration in minutes
        """
        try:
            avg_duration = db.session.query(
                func.avg(ParkingSession.duration_minutes)
            ).filter(
                ParkingSession.is_active == False,
                ParkingSession.duration_minutes.isnot(None)
            ).scalar()
            
            return round(avg_duration, 2) if avg_duration else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating average session duration: {e}")
            return 0.0
    
    def get_peak_hours(self, date=None):
        """
        Get peak hours for parking based on entry detections
        
        Args:
            date (datetime.date, optional): Date to analyze (default: today)
            
        Returns:
            list: List of hours with highest activity
        """
        try:
            if date is None:
                date = datetime.now().date()
            
            hourly_data = self.get_hourly_occupancy(date)
            
            if not hourly_data:
                return []
            
            # Sort by count descending and get top 3 hours
            sorted_hours = sorted(hourly_data, key=lambda x: x.count, reverse=True)
            peak_hours = [int(hour.hour) for hour in sorted_hours[:3]]
            
            return peak_hours
            
        except Exception as e:
            self.logger.error(f"Error calculating peak hours: {e}")
            return []
    
    def get_revenue_summary(self, days=7):
        """
        Get comprehensive revenue summary
        
        Args:
            days (int): Number of days to analyze
            
        Returns:
            dict: Dictionary containing revenue summary
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            total_revenue = self.get_total_revenue(start_date, end_date)
            daily_revenue = self.get_daily_revenue(days)
            
            # Calculate average daily revenue
            avg_daily_revenue = total_revenue / days if days > 0 else 0
            
            # Get today's revenue
            today = datetime.now().date()
            today_revenue = self.get_total_revenue(
                datetime.combine(today, datetime.min.time()),
                datetime.combine(today, datetime.max.time())
            )
            
            return {
                'total_revenue': round(total_revenue, 2),
                'avg_daily_revenue': round(avg_daily_revenue, 2),
                'today_revenue': round(today_revenue, 2),
                'daily_breakdown': daily_revenue,
                'period_days': days
            }
            
        except Exception as e:
            self.logger.error(f"Error generating revenue summary: {e}")
            return {
                'total_revenue': 0.0,
                'avg_daily_revenue': 0.0,
                'today_revenue': 0.0,
                'daily_breakdown': [],
                'period_days': days
            }
    
    def get_vehicle_statistics(self):
        """
        Get comprehensive vehicle statistics
        
        Returns:
            dict: Dictionary containing vehicle statistics
        """
        try:
            total_vehicles = Vehicle.query.count()
            active_sessions = ParkingSession.query.filter_by(is_active=True).count()
            completed_sessions = ParkingSession.query.filter_by(is_active=False).count()
            
            # Calculate average visits per vehicle
            avg_visits = db.session.query(
                func.avg(Vehicle.total_visits)
            ).scalar()
            
            return {
                'total_vehicles': total_vehicles,
                'active_sessions': active_sessions,
                'completed_sessions': completed_sessions,
                'avg_visits_per_vehicle': round(avg_visits, 2) if avg_visits else 0.0
            }
            
        except Exception as e:
            self.logger.error(f"Error generating vehicle statistics: {e}")
            return {
                'total_vehicles': 0,
                'active_sessions': 0,
                'completed_sessions': 0,
                'avg_visits_per_vehicle': 0.0
            }
    
    def get_detection_statistics(self, days=7):
        """
        Get detection statistics for a period
        
        Args:
            days (int): Number of days to analyze
            
        Returns:
            dict: Dictionary containing detection statistics
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            total_detections = DetectionLog.query.filter(
                DetectionLog.timestamp.between(start_date, end_date)
            ).count()
            
            license_plate_detections = DetectionLog.query.filter(
                DetectionLog.timestamp.between(start_date, end_date),
                DetectionLog.detection_type == 'license_plate'
            ).count()
            
            avg_confidence = db.session.query(
                func.avg(DetectionLog.confidence)
            ).filter(
                DetectionLog.timestamp.between(start_date, end_date),
                DetectionLog.confidence.isnot(None)
            ).scalar()
            
            return {
                'total_detections': total_detections,
                'license_plate_detections': license_plate_detections,
                'avg_confidence': round(avg_confidence * 100, 2) if avg_confidence else 0.0,
                'period_days': days
            }
            
        except Exception as e:
            self.logger.error(f"Error generating detection statistics: {e}")
            return {
                'total_detections': 0,
                'license_plate_detections': 0,
                'avg_confidence': 0.0,
                'period_days': days
            }