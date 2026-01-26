"""
Dashboard service - handles all business logic for dashboard functionality
"""
from datetime import datetime
from sqlalchemy import func, desc
from app import db
from models import ParkingSpace, ParkingSession, DetectionLog


class DashboardService:
    """Service class for dashboard-related operations"""
    
    @staticmethod
    def get_parking_statistics():
        """
        Get current parking statistics
        
        Returns:
            dict: Dictionary containing parking statistics
        """
        total_spaces = ParkingSpace.query.count()
        occupied_spaces = ParkingSpace.query.filter_by(is_occupied=True).count()
        available_spaces = total_spaces - occupied_spaces
        
        return {
            'total_spaces': total_spaces,
            'occupied_spaces': occupied_spaces,
            'available_spaces': available_spaces
        }
    
    @staticmethod
    def get_active_sessions():
        """
        Get all active parking sessions
        
        Returns:
            list: List of active ParkingSession objects
        """
        return ParkingSession.query.filter_by(is_active=True).all()
    
    @staticmethod
    def get_recent_detections(limit=10):
        """
        Get recent detection logs
        
        Args:
            limit (int): Maximum number of detections to return
            
        Returns:
            list: List of recent DetectionLog objects
        """
        return DetectionLog.query.order_by(desc(DetectionLog.timestamp)).limit(limit).all()
    
    @staticmethod
    def get_today_revenue():
        """
        Calculate today's total revenue from completed parking sessions
        
        Returns:
            float: Total revenue for today
        """
        today = datetime.now().date()
        revenue = db.session.query(func.sum(ParkingSession.toll_amount)).filter(
            func.date(ParkingSession.exit_time) == today,
            ParkingSession.is_active == False
        ).scalar()
        
        return revenue or 0.0
    
    @staticmethod
    def get_dashboard_data():
        """
        Get all data needed for dashboard display
        
        Returns:
            dict: Dictionary containing all dashboard data
        """
        statistics = DashboardService.get_parking_statistics()
        active_sessions = DashboardService.get_active_sessions()
        recent_detections = DashboardService.get_recent_detections()
        today_revenue = DashboardService.get_today_revenue()
        
        return {
            'total_spaces': statistics['total_spaces'],
            'occupied_spaces': statistics['occupied_spaces'],
            'available_spaces': statistics['available_spaces'],
            'active_sessions': active_sessions,
            'recent_detections': recent_detections,
            'today_revenue': today_revenue
        }
    
    @staticmethod
    def calculate_session_duration(entry_time):
        """
        Calculate duration of a parking session
        
        Args:
            entry_time (datetime): Session entry time
            
        Returns:
            dict: Dictionary containing hours and minutes
        """
        now = datetime.now()
        duration = now - entry_time
        total_minutes = int(duration.total_seconds() / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        return {
            'hours': hours,
            'minutes': minutes,
            'total_minutes': total_minutes
        }
    
    @staticmethod
    def calculate_estimated_cost(entry_time):
        """
        Calculate estimated cost for an ongoing parking session
        
        Args:
            entry_time (datetime): Session entry time
            
        Returns:
            float: Estimated cost in NPR
        """
        duration = DashboardService.calculate_session_duration(entry_time)
        total_minutes = duration['total_minutes']
        
        if total_minutes <= 60:
            return 50.0  # Rs. 50 for first hour
        else:
            additional_hours = ((total_minutes - 60) // 60) + (1 if (total_minutes - 60) % 60 > 0 else 0)
            return 50.0 + (additional_hours * 30.0)  # Rs. 30 per additional hour