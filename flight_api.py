import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
from config import Config
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FlightSegment:
    """Represents a flight segment (one leg of a journey)"""
    airline_code: str
    airline_name: str
    flight_number: str
    origin: str
    destination: str
    departure_datetime: datetime
    arrival_datetime: datetime
    aircraft: str = ""
    cabin_class: str = "economy"

@dataclass  
class FlightOffer:
    """Represents a complete flight offer (may have multiple segments)"""
    segments: List[FlightSegment]
    total_price: float
    currency: str
    booking_url: str
    duration_minutes: int
    stops: int
    layover_airports: List[str]
    layover_durations: List[int]  # in minutes
    convenience_score: float = 0.0
    is_available: bool = True

class FlightSearchEngine:
    """Main flight search engine with multiple API integrations"""
    
    def __init__(self):
        self.amadeus_token = None
        self.amadeus_token_expires = None
        self.last_api_call = 0
        self.api_call_interval = 1.0  # Minimum seconds between API calls
        
    def _get_amadeus_token(self) -> Optional[str]:
        """Get OAuth token for Amadeus API"""
        if (self.amadeus_token and self.amadeus_token_expires and 
            datetime.now() < self.amadeus_token_expires):
            return self.amadeus_token
            
        if not Config.AMADEUS_API_KEY or not Config.AMADEUS_API_SECRET:
            logger.warning("Amadeus API credentials not configured")
            return None
            
        url = "https://api.amadeus.com/v1/security/oauth2/token"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'grant_type': 'client_credentials',
            'client_id': Config.AMADEUS_API_KEY,
            'client_secret': Config.AMADEUS_API_SECRET
        }
        
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            self.amadeus_token = token_data['access_token']
            # Token expires in seconds, add buffer
            expires_in = token_data.get('expires_in', 3600) - 60
            self.amadeus_token_expires = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info("Amadeus API token obtained successfully")
            return self.amadeus_token
            
        except Exception as e:
            logger.error(f"Failed to get Amadeus token: {e}")
            return None
    
    def _rate_limit_delay(self):
        """Implement rate limiting between API calls"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        if time_since_last_call < self.api_call_interval:
            time.sleep(self.api_call_interval - time_since_last_call)
        self.last_api_call = time.time()
    
    def search_amadeus_flights(self, origin: str, destination: str, departure_date: str,
                              return_date: str = None, adults: int = 1) -> List[FlightOffer]:
        """Search flights using Amadeus API"""
        token = self._get_amadeus_token()
        if not token:
            return []
            
        self._rate_limit_delay()
        
        url = "https://api.amadeus.com/v2/shopping/flight-offers"
        headers = {'Authorization': f'Bearer {token}'}
        
        params = {
            'originLocationCode': origin,
            'destinationLocationCode': destination,
            'departureDate': departure_date,
            'adults': adults,
            'max': 50,  # Maximum results
            'currencyCode': 'USD'
        }
        
        if return_date:
            params['returnDate'] = return_date
            
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            return self._parse_amadeus_response(data)
            
        except Exception as e:
            logger.error(f"Amadeus API search failed: {e}")
            return []
    
    def _parse_amadeus_response(self, data: Dict) -> List[FlightOffer]:
        """Parse Amadeus API response into FlightOffer objects"""
        offers = []
        
        if 'data' not in data:
            return offers
            
        for offer_data in data['data']:
            try:
                # Extract price information
                price = float(offer_data['price']['total'])
                currency = offer_data['price']['currency']
                
                # Parse itinerary segments
                segments = []
                layover_airports = []
                layover_durations = []
                total_duration = 0
                
                for itinerary in offer_data['itineraries']:
                    duration_str = itinerary.get('duration', 'PT0M')
                    duration_minutes = self._parse_duration(duration_str)
                    total_duration += duration_minutes
                    
                    prev_arrival = None
                    for i, segment_data in enumerate(itinerary['segments']):
                        # Create flight segment
                        segment = FlightSegment(
                            airline_code=segment_data['carrierCode'],
                            airline_name=self._get_airline_name(segment_data['carrierCode']),
                            flight_number=f"{segment_data['carrierCode']}{segment_data['number']}",
                            origin=segment_data['departure']['iataCode'],
                            destination=segment_data['arrival']['iataCode'],
                            departure_datetime=datetime.fromisoformat(segment_data['departure']['at'].replace('Z', '+00:00')),
                            arrival_datetime=datetime.fromisoformat(segment_data['arrival']['at'].replace('Z', '+00:00')),
                            aircraft=segment_data.get('aircraft', {}).get('code', ''),
                            cabin_class=segment_data.get('cabin', 'economy')
                        )
                        segments.append(segment)
                        
                        # Calculate layover if this isn't the first segment
                        if prev_arrival and i > 0:
                            layover_minutes = int((segment.departure_datetime - prev_arrival).total_seconds() / 60)
                            if layover_minutes > 0:
                                layover_airports.append(segment.origin)
                                layover_durations.append(layover_minutes)
                        
                        prev_arrival = segment.arrival_datetime
                
                # Calculate stops (number of layovers)
                stops = len(layover_airports)
                
                # Create booking URL (simplified - would need real deep link)
                booking_url = f"https://www.amadeus.com/book?offer={offer_data.get('id', '')}"
                
                offer = FlightOffer(
                    segments=segments,
                    total_price=price,
                    currency=currency,
                    booking_url=booking_url,
                    duration_minutes=total_duration,
                    stops=stops,
                    layover_airports=layover_airports,
                    layover_durations=layover_durations
                )
                
                offers.append(offer)
                
            except Exception as e:
                logger.warning(f"Failed to parse offer: {e}")
                continue
        
        logger.info(f"Parsed {len(offers)} flight offers from Amadeus")
        return offers
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration string to minutes (e.g., 'PT2H30M' -> 150)"""
        try:
            # Remove PT prefix
            duration_str = duration_str.replace('PT', '')
            
            hours = 0
            minutes = 0
            
            if 'H' in duration_str:
                parts = duration_str.split('H')
                hours = int(parts[0])
                duration_str = parts[1]
            
            if 'M' in duration_str:
                minutes = int(duration_str.replace('M', ''))
            
            return hours * 60 + minutes
            
        except:
            return 0
    
    def _get_airline_name(self, airline_code: str) -> str:
        """Get airline name from code (simplified mapping)"""
        airline_names = {
            'AA': 'American Airlines',
            'DL': 'Delta Air Lines', 
            'UA': 'United Airlines',
            'WN': 'Southwest Airlines',
            'AS': 'Alaska Airlines',
            'B6': 'JetBlue Airways',
            'NK': 'Spirit Airlines',
            'F9': 'Frontier Airlines',
            'HA': 'Hawaiian Airlines',
            'SY': 'Sun Country Airlines'
        }
        return airline_names.get(airline_code, airline_code)
    
    def search_rapidapi_flights(self, origin: str, destination: str, departure_date: str) -> List[FlightOffer]:
        """Search flights using RapidAPI as fallback"""
        if not Config.RAPIDAPI_KEY:
            logger.warning("RapidAPI key not configured")
            return []
            
        # This is a simplified implementation - would need to integrate with specific RapidAPI flight service
        # Example: Skyscanner, Kayak, or other flight search APIs available on RapidAPI
        logger.info("RapidAPI flight search not yet implemented")
        return []
    
    def generate_mock_flights(self, origin: str, destination: str, departure_date: str,
                             return_date: str = None) -> List[FlightOffer]:
        """Generate mock flight data for development/demo purposes"""
        logger.info(f"Generating mock flights for {origin} -> {destination}")
        
        flights = []
        base_date = datetime.fromisoformat(departure_date)
        
        # Generate 8-12 realistic flight options
        airlines = [
            ('AA', 'American Airlines'),
            ('DL', 'Delta Air Lines'),
            ('UA', 'United Airlines'),
            ('WN', 'Southwest Airlines'),
            ('AS', 'Alaska Airlines'),
            ('B6', 'JetBlue Airways')
        ]
        
        for i in range(np.random.randint(8, 13)):
            airline_code, airline_name = np.random.choice(airlines)[0], np.random.choice(airlines)[1]
            
            # Generate realistic departure times (6 AM to 10 PM)
            departure_hour = np.random.randint(6, 23)
            departure_minute = np.random.choice([0, 15, 30, 45])
            departure_dt = base_date.replace(hour=departure_hour, minute=departure_minute)
            
            # Generate flight duration based on rough distance estimates
            base_duration = self._estimate_flight_duration(origin, destination)
            duration_variation = np.random.randint(-30, 60)
            total_duration = max(base_duration + duration_variation, 60)
            
            # Determine if flight has stops
            stops = np.random.choice([0, 1, 2], p=[0.4, 0.5, 0.1])  # 40% direct, 50% 1-stop, 10% 2-stop
            
            layover_airports = []
            layover_durations = []
            segments = []
            
            if stops == 0:
                # Direct flight
                arrival_dt = departure_dt + timedelta(minutes=total_duration)
                segment = FlightSegment(
                    airline_code=airline_code,
                    airline_name=airline_name,
                    flight_number=f"{airline_code}{np.random.randint(100, 9999)}",
                    origin=origin,
                    destination=destination,
                    departure_datetime=departure_dt,
                    arrival_datetime=arrival_dt
                )
                segments.append(segment)
                
            else:
                # Flight with stops
                hub_airports = self._get_likely_hubs(origin, destination)
                current_origin = origin
                current_time = departure_dt
                
                for stop_num in range(stops + 1):
                    if stop_num == stops:
                        # Final segment to destination
                        segment_destination = destination
                    else:
                        # Intermediate stop
                        segment_destination = np.random.choice(hub_airports)
                        layover_airports.append(segment_destination)
                    
                    # Segment duration
                    segment_duration = np.random.randint(60, 180)
                    segment_arrival = current_time + timedelta(minutes=segment_duration)
                    
                    segment = FlightSegment(
                        airline_code=airline_code,
                        airline_name=airline_name,
                        flight_number=f"{airline_code}{np.random.randint(100, 9999)}",
                        origin=current_origin,
                        destination=segment_destination,
                        departure_datetime=current_time,
                        arrival_datetime=segment_arrival
                    )
                    segments.append(segment)
                    
                    # Add layover time if not the final segment
                    if stop_num < stops:
                        layover_duration = np.random.randint(45, 180)  # 45min to 3 hours
                        layover_durations.append(layover_duration)
                        current_time = segment_arrival + timedelta(minutes=layover_duration)
                        current_origin = segment_destination
                    
                    total_duration += segment_duration
                    if stop_num < stops:
                        total_duration += layover_durations[-1]
            
            # Generate realistic pricing
            base_price = self._estimate_base_price(origin, destination)
            price_variation = np.random.uniform(0.7, 1.4)  # ±40% variation
            stops_penalty = stops * np.random.uniform(0.9, 1.1)  # Small penalty for stops
            final_price = base_price * price_variation * (1 + stops_penalty * 0.1)
            
            # Round to realistic price increments
            final_price = round(final_price / 10) * 10
            
            # Create booking URL (mock)
            booking_url = f"https://book.{airline_code.lower()}.com/flight/{departure_date}/{origin}-{destination}"
            
            offer = FlightOffer(
                segments=segments,
                total_price=final_price,
                currency='USD',
                booking_url=booking_url,
                duration_minutes=total_duration,
                stops=stops,
                layover_airports=layover_airports,
                layover_durations=layover_durations
            )
            
            flights.append(offer)
        
        # Sort by price to make primary recommendation the cheapest
        flights.sort(key=lambda x: x.total_price)
        
        logger.info(f"Generated {len(flights)} mock flights")
        return flights
    
    def _estimate_flight_duration(self, origin: str, destination: str) -> int:
        """Estimate flight duration in minutes based on airport pairs"""
        # Simplified duration estimates (in minutes)
        duration_estimates = {
            ('LAX', 'PHX'): 70, ('PHX', 'LAX'): 70,
            ('LAX', 'TUS'): 80, ('TUS', 'LAX'): 80,
            ('BUR', 'PHX'): 75, ('PHX', 'BUR'): 75,
            ('SNA', 'PHX'): 75, ('PHX', 'SNA'): 75,
            ('LGB', 'PHX'): 75, ('PHX', 'LGB'): 75,
        }
        
        # Default duration if pair not found
        return duration_estimates.get((origin, destination), 120)
    
    def _estimate_base_price(self, origin: str, destination: str) -> float:
        """Estimate base price for route"""
        # Simplified price estimates based on route popularity and distance
        base_prices = {
            ('LAX', 'PHX'): 180, ('PHX', 'LAX'): 180,
            ('LAX', 'TUS'): 220, ('TUS', 'LAX'): 220,
            ('BUR', 'PHX'): 160, ('PHX', 'BUR'): 160,
            ('SNA', 'PHX'): 190, ('PHX', 'SNA'): 190,
            ('LGB', 'PHX'): 170, ('PHX', 'LGB'): 170,
        }
        
        return base_prices.get((origin, destination), 250)
    
    def _get_likely_hubs(self, origin: str, destination: str) -> List[str]:
        """Get likely hub airports for connecting flights"""
        major_hubs = ['DEN', 'DFW', 'ORD', 'ATL', 'PHX', 'LAX', 'SFO', 'SEA', 'LAS']
        
        # Remove origin and destination from hub list
        hubs = [h for h in major_hubs if h not in [origin, destination]]
        
        return hubs
    
    def search_flights(self, origin: str, destination: str, departure_date: str,
                      return_date: str = None, adults: int = 1) -> List[FlightOffer]:
        """Main flight search method that tries multiple data sources"""
        flights = []
        
        # Try Amadeus API first
        try:
            amadeus_flights = self.search_amadeus_flights(origin, destination, departure_date, return_date, adults)
            if amadeus_flights:
                flights.extend(amadeus_flights)
                logger.info(f"Retrieved {len(amadeus_flights)} flights from Amadeus")
        except Exception as e:
            logger.error(f"Amadeus search failed: {e}")
        
        # If no flights from Amadeus, try RapidAPI
        if not flights:
            try:
                rapidapi_flights = self.search_rapidapi_flights(origin, destination, departure_date)
                if rapidapi_flights:
                    flights.extend(rapidapi_flights)
                    logger.info(f"Retrieved {len(rapidapi_flights)} flights from RapidAPI")
            except Exception as e:
                logger.error(f"RapidAPI search failed: {e}")
        
        # If still no flights, generate mock data for demo
        if not flights:
            flights = self.generate_mock_flights(origin, destination, departure_date, return_date)
        
        return flights
    
    def get_flexible_date_options(self, origin: str, destination: str, preferred_date: str,
                                 days_range: int = 3) -> Dict[str, List[FlightOffer]]:
        """Search flights across multiple dates for flexible options"""
        base_date = datetime.fromisoformat(preferred_date)
        date_options = {}
        
        for offset in range(-days_range, days_range + 1):
            search_date = base_date + timedelta(days=offset)
            date_str = search_date.strftime('%Y-%m-%d')
            
            flights = self.search_flights(origin, destination, date_str)
            if flights:
                # Keep only the cheapest flight for each date to reduce clutter
                date_options[date_str] = [min(flights, key=lambda x: x.total_price)]
        
        return date_options