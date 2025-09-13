import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from config import Config
import json

class FlightDatabase:
    """SQLite database manager for flight price history and user preferences"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_database()
    
    def init_database(self):
        """Initialize database tables if they don't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS flight_searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date DATE NOT NULL,
                    return_date DATE,
                    adult_count INTEGER DEFAULT 1,
                    search_hash TEXT UNIQUE
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS flight_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_id INTEGER,
                    airline_code TEXT,
                    airline_name TEXT,
                    flight_number TEXT,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_datetime DATETIME,
                    arrival_datetime DATETIME,
                    duration_minutes INTEGER,
                    stops INTEGER DEFAULT 0,
                    layover_airports TEXT,  -- JSON array of airport codes
                    layover_durations TEXT, -- JSON array of minutes
                    price_usd DECIMAL(10,2) NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    booking_url TEXT,
                    cabin_class TEXT DEFAULT 'economy',
                    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_available BOOLEAN DEFAULT 1,
                    convenience_score DECIMAL(5,2),  -- Calculated convenience score
                    FOREIGN KEY (search_id) REFERENCES flight_searches (id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    departure_airport TEXT,
                    preferred_destinations TEXT,  -- JSON array
                    max_price DECIMAL(10,2),
                    max_duration_hours INTEGER,
                    prefer_direct BOOLEAN,
                    max_layover_duration INTEGER,
                    exclude_redeye BOOLEAN,
                    preferred_departure_time TEXT,
                    email_notifications BOOLEAN,
                    price_alert_threshold DECIMAL(10,2),
                    busy_dates TEXT,  -- JSON array of ISO date strings
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    target_price DECIMAL(10,2),
                    current_price DECIMAL(10,2),
                    price_drop_amount DECIMAL(10,2),
                    price_drop_percent DECIMAL(5,2),
                    alert_sent BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    triggered_at DATETIME
                )
            ''')
            
            # Create indexes for better query performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_flight_prices_route ON flight_prices (origin, destination)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_flight_prices_date ON flight_prices (departure_datetime)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_flight_prices_price ON flight_prices (price_usd)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_searches_hash ON flight_searches (search_hash)')
    
    def save_flight_search(self, origin: str, destination: str, departure_date: str, 
                          return_date: str = None, adult_count: int = 1) -> int:
        """Save a new flight search and return the search ID"""
        search_hash = f"{origin}_{destination}_{departure_date}_{return_date}_{adult_count}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO flight_searches 
                    (origin, destination, departure_date, return_date, adult_count, search_hash)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (origin, destination, departure_date, return_date, adult_count, search_hash))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Search already exists, get the existing ID
                cursor.execute('SELECT id FROM flight_searches WHERE search_hash = ?', (search_hash,))
                return cursor.fetchone()[0]
    
    def save_flight_prices(self, search_id: int, flights: List[Dict]) -> int:
        """Save flight price data for a search"""
        saved_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            for flight in flights:
                # Convert layover data to JSON strings
                layover_airports = json.dumps(flight.get('layover_airports', []))
                layover_durations = json.dumps(flight.get('layover_durations', []))
                
                conn.execute('''
                    INSERT INTO flight_prices 
                    (search_id, airline_code, airline_name, flight_number, origin, destination,
                     departure_datetime, arrival_datetime, duration_minutes, stops, 
                     layover_airports, layover_durations, price_usd, currency, booking_url,
                     cabin_class, convenience_score, is_available)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    search_id,
                    flight.get('airline_code'),
                    flight.get('airline_name'), 
                    flight.get('flight_number'),
                    flight.get('origin'),
                    flight.get('destination'),
                    flight.get('departure_datetime'),
                    flight.get('arrival_datetime'),
                    flight.get('duration_minutes'),
                    flight.get('stops', 0),
                    layover_airports,
                    layover_durations,
                    flight.get('price_usd'),
                    flight.get('currency', 'USD'),
                    flight.get('booking_url'),
                    flight.get('cabin_class', 'economy'),
                    flight.get('convenience_score'),
                    flight.get('is_available', True)
                ))
                saved_count += 1
        
        return saved_count
    
    def get_price_history(self, origin: str, destination: str, days: int = 30) -> pd.DataFrame:
        """Get price history for a route over the specified number of days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            query = '''
                SELECT 
                    fp.recorded_at,
                    fp.departure_datetime,
                    fp.price_usd,
                    fp.airline_name,
                    fp.duration_minutes,
                    fp.stops,
                    fp.convenience_score
                FROM flight_prices fp
                JOIN flight_searches fs ON fp.search_id = fs.id  
                WHERE fp.origin = ? AND fp.destination = ?
                AND fp.recorded_at >= ?
                AND fp.is_available = 1
                ORDER BY fp.recorded_at DESC
            '''
            return pd.read_sql_query(query, conn, params=(origin, destination, cutoff_date))
    
    def get_cheapest_flights(self, origin: str, destination: str, limit: int = 5) -> List[Dict]:
        """Get the cheapest available flights for a route"""
        with sqlite3.connect(self.db_path) as conn:
            # Get most recent search data
            query = '''
                SELECT 
                    fp.airline_code, fp.airline_name, fp.flight_number,
                    fp.origin, fp.destination, fp.departure_datetime, fp.arrival_datetime,
                    fp.duration_minutes, fp.stops, fp.layover_airports, fp.layover_durations,
                    fp.price_usd, fp.booking_url, fp.convenience_score, fp.recorded_at
                FROM flight_prices fp
                JOIN flight_searches fs ON fp.search_id = fs.id
                WHERE fp.origin = ? AND fp.destination = ?
                AND fp.is_available = 1
                AND DATE(fp.recorded_at) = (
                    SELECT DATE(MAX(recorded_at)) FROM flight_prices 
                    WHERE origin = ? AND destination = ?
                )
                ORDER BY fp.price_usd ASC
                LIMIT ?
            '''
            
            cursor = conn.cursor()
            cursor.execute(query, (origin, destination, origin, destination, limit))
            
            flights = []
            for row in cursor.fetchall():
                flight = {
                    'airline_code': row[0],
                    'airline_name': row[1], 
                    'flight_number': row[2],
                    'origin': row[3],
                    'destination': row[4],
                    'departure_datetime': row[5],
                    'arrival_datetime': row[6],
                    'duration_minutes': row[7],
                    'stops': row[8],
                    'layover_airports': json.loads(row[9]) if row[9] else [],
                    'layover_durations': json.loads(row[10]) if row[10] else [],
                    'price_usd': float(row[11]),
                    'booking_url': row[12],
                    'convenience_score': float(row[13]) if row[13] else None,
                    'recorded_at': row[14]
                }
                flights.append(flight)
            
            return flights
    
    def save_user_preferences(self, preferences: Dict) -> None:
        """Save or update user preferences"""
        with sqlite3.connect(self.db_path) as conn:
            # Convert arrays to JSON strings
            preferred_destinations = json.dumps(preferences.get('preferred_destinations', []))
            busy_dates = json.dumps(preferences.get('busy_dates', []))
            
            # Delete existing preferences (simple approach - could be made more sophisticated)
            conn.execute('DELETE FROM user_preferences')
            
            # Insert new preferences
            conn.execute('''
                INSERT INTO user_preferences
                (departure_airport, preferred_destinations, max_price, max_duration_hours,
                 prefer_direct, max_layover_duration, exclude_redeye, preferred_departure_time,
                 email_notifications, price_alert_threshold, busy_dates)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                preferences.get('departure_airport'),
                preferred_destinations,
                preferences.get('max_price'),
                preferences.get('max_duration_hours'),
                preferences.get('prefer_direct'),
                preferences.get('max_layover_duration'),
                preferences.get('exclude_redeye'),
                preferences.get('preferred_departure_time'),
                preferences.get('email_notifications'),
                preferences.get('price_alert_threshold'),
                busy_dates
            ))
    
    def get_user_preferences(self) -> Optional[Dict]:
        """Get current user preferences"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user_preferences ORDER BY updated_at DESC LIMIT 1')
            row = cursor.fetchone()
            
            if not row:
                return None
            
            # Map database columns to preference dictionary
            prefs = {
                'departure_airport': row[1],
                'preferred_destinations': json.loads(row[2]) if row[2] else [],
                'max_price': float(row[3]) if row[3] else None,
                'max_duration_hours': row[4],
                'prefer_direct': bool(row[5]),
                'max_layover_duration': row[6],
                'exclude_redeye': bool(row[7]),
                'preferred_departure_time': row[8],
                'email_notifications': bool(row[9]),
                'price_alert_threshold': float(row[10]) if row[10] else None,
                'busy_dates': json.loads(row[11]) if row[11] else [],
                'created_at': row[12],
                'updated_at': row[13]
            }
            
            return prefs
    
    def create_price_alert(self, origin: str, destination: str, current_price: float,
                          target_price: float, drop_amount: float, drop_percent: float) -> int:
        """Create a new price alert"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO price_alerts 
                (origin, destination, target_price, current_price, 
                 price_drop_amount, price_drop_percent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (origin, destination, target_price, current_price, drop_amount, drop_percent))
            return cursor.lastrowid
    
    def mark_alert_sent(self, alert_id: int) -> None:
        """Mark a price alert as sent"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE price_alerts 
                SET alert_sent = 1, triggered_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (alert_id,))
    
    def get_pending_alerts(self) -> List[Dict]:
        """Get unsent price alerts"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, origin, destination, target_price, current_price,
                       price_drop_amount, price_drop_percent, created_at
                FROM price_alerts 
                WHERE alert_sent = 0
                ORDER BY created_at DESC
            ''')
            
            alerts = []
            for row in cursor.fetchall():
                alert = {
                    'id': row[0],
                    'origin': row[1],
                    'destination': row[2], 
                    'target_price': float(row[3]),
                    'current_price': float(row[4]),
                    'price_drop_amount': float(row[5]),
                    'price_drop_percent': float(row[6]),
                    'created_at': row[7]
                }
                alerts.append(alert)
                
            return alerts
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> None:
        """Remove old flight price data to keep database size manageable"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with sqlite3.connect(self.db_path) as conn:
            # Delete old flight prices
            conn.execute('DELETE FROM flight_prices WHERE recorded_at < ?', (cutoff_date,))
            
            # Delete searches with no remaining prices
            conn.execute('''
                DELETE FROM flight_searches 
                WHERE id NOT IN (SELECT DISTINCT search_id FROM flight_prices)
            ''')
            
            # Delete old alerts
            conn.execute('DELETE FROM price_alerts WHERE created_at < ? AND alert_sent = 1', (cutoff_date,))