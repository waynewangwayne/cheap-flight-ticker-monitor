import os
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration settings for the flight monitor application"""
    
    # API Keys
    AMADEUS_API_KEY = os.getenv('AMADEUS_API_KEY', '')
    AMADEUS_API_SECRET = os.getenv('AMADEUS_API_SECRET', '')
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '')
    
    # Email Configuration
    EMAIL_SENDER = os.getenv('EMAIL_SENDER', '')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
    EMAIL_RECIPIENT = os.getenv('EMAIL_RECIPIENT', '')
    
    # Database Configuration
    DATABASE_PATH = 'flight_monitor.db'
    
    # Flight Search Configuration
    MAX_ALTERNATIVES = 5
    FLEXIBLE_DAYS = 3  # ±3 days from optimal date
    
    # Layover Optimization Settings
    MIN_LAYOVER_MINUTES = 90   # Minimum connection time
    MAX_LAYOVER_MINUTES = 240  # Maximum preferred layover
    MAX_TRANSFERS = 2          # Never more than 2 stops
    
    # Ranking Algorithm Weights
    WEIGHT_PRICE = 0.40        # 40% price importance
    WEIGHT_DURATION = 0.30     # 30% travel time importance  
    WEIGHT_STOPS = 0.20        # 20% number of stops importance
    WEIGHT_LAYOVER_QUALITY = 0.10  # 10% layover convenience importance
    
    # Price Alert Thresholds
    PRICE_DROP_THRESHOLD_PCT = 15  # Alert when price drops 15% or more
    PRICE_DROP_THRESHOLD_ABS = 50  # Alert when price drops $50 or more
    
    # Supported Airports
    ARIZONA_AIRPORTS = {
        'PHX': 'Phoenix Sky Harbor International',
        'TUS': 'Tucson International Airport',
        'FLG': 'Flagstaff Pulliam Field'
    }
    
    LA_AIRPORTS = {
        'LAX': 'Los Angeles International',
        'BUR': 'Hollywood Burbank Airport', 
        'LGB': 'Long Beach Airport',
        'SNA': 'John Wayne Airport (Orange County)'
    }
    
    # Major Hub Airports (for layover quality scoring)
    MAJOR_HUBS = [
        'ATL', 'ORD', 'DFW', 'DEN', 'LAX', 'PHX', 'LAS', 'DTW',
        'MSP', 'SEA', 'EWR', 'JFK', 'LGA', 'BOS', 'IAD', 'DCA',
        'MIA', 'FLL', 'MCO', 'SFO', 'SJC', 'PDX', 'SLC'
    ]
    
    # Airlines to prioritize (can be customized by user)
    PREFERRED_AIRLINES = []
    
    # Airlines to avoid (can be customized by user)  
    BLACKLISTED_AIRLINES = []
    
    # Mobile Interface Settings
    AUTO_REFRESH_SECONDS = 300  # 5 minutes default
    MAX_MOBILE_CARDS = 5       # Max flight cards to show on mobile
    
    @classmethod
    def get_all_destination_airports(cls) -> Dict[str, str]:
        """Get all supported destination airports"""
        return {**cls.ARIZONA_AIRPORTS, **cls.LA_AIRPORTS}
    
    @classmethod
    def is_major_hub(cls, airport_code: str) -> bool:
        """Check if airport is a major hub for layover quality scoring"""
        return airport_code.upper() in cls.MAJOR_HUBS
    
    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate configuration and return any missing required settings"""
        missing = []
        
        if not cls.AMADEUS_API_KEY:
            missing.append("AMADEUS_API_KEY")
        if not cls.AMADEUS_API_SECRET:
            missing.append("AMADEUS_API_SECRET")
            
        return missing

# Default user preferences (can be overridden via UI)
DEFAULT_PREFERENCES = {
    'departure_airport': '',  # To be set by user
    'preferred_destinations': ['PHX', 'LAX'],  # Default to primary airports
    'max_price': 1000,  # Maximum acceptable price
    'max_duration_hours': 12,  # Maximum total travel time
    'prefer_direct': True,  # Prefer direct flights when possible
    'max_layover_duration': 4,  # Hours
    'exclude_redeye': True,  # Avoid red-eye flights
    'preferred_departure_time': 'morning',  # morning, afternoon, evening
    'email_notifications': True,
    'price_alert_threshold': 50  # Dollar amount for price alerts
}