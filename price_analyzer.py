import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging
from config import Config
from flight_api import FlightOffer

logger = logging.getLogger(__name__)

@dataclass
class FlightScore:
    """Comprehensive scoring for flight options"""
    price_score: float
    duration_score: float
    stops_score: float
    layover_score: float
    convenience_score: float
    total_score: float
    rank: int = 0
    is_primary_choice: bool = False
    is_alternative: bool = False

@dataclass
class FlightAnalysis:
    """Analysis results for a set of flight options"""
    primary_option: FlightOffer
    alternatives: List[FlightOffer] = field(default_factory=list)
    flexible_dates: Dict[str, FlightOffer] = field(default_factory=dict)
    price_statistics: Dict = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

class LayoverOptimizer:
    """Optimize flight options based on layover quality and connection times"""
    
    @staticmethod
    def evaluate_layover_quality(layover_airports: List[str], layover_durations: List[int]) -> float:
        """
        Evaluate layover quality based on airport and duration
        Returns score from 0.0 (worst) to 1.0 (best)
        """
        if not layover_airports:
            return 1.0  # Direct flight gets perfect score
        
        total_score = 0.0
        
        for airport, duration in zip(layover_airports, layover_durations):
            # Duration score (optimal range: 90-180 minutes)
            if duration < Config.MIN_LAYOVER_MINUTES:
                duration_score = 0.1  # Very risky short connection
            elif duration > Config.MAX_LAYOVER_MINUTES:
                duration_score = 0.6  # Long but manageable
            else:
                # Optimal range gets higher scores
                optimal_duration = (Config.MIN_LAYOVER_MINUTES + Config.MAX_LAYOVER_MINUTES) / 2
                distance_from_optimal = abs(duration - optimal_duration)
                max_distance = Config.MAX_LAYOVER_MINUTES - Config.MIN_LAYOVER_MINUTES
                duration_score = 1.0 - (distance_from_optimal / max_distance) * 0.4
            
            # Airport quality score
            if Config.is_major_hub(airport):
                airport_score = 0.9  # Major hubs have good facilities
            else:
                airport_score = 0.6  # Smaller airports may have fewer amenities
            
            # Combined score for this layover
            layover_score = (duration_score * 0.7) + (airport_score * 0.3)
            total_score += layover_score
        
        # Average across all layovers
        return total_score / len(layover_airports)
    
    @staticmethod
    def filter_problematic_connections(flights: List[FlightOffer]) -> List[FlightOffer]:
        """Filter out flights with problematic connections"""
        filtered_flights = []
        
        for flight in flights:
            is_acceptable = True
            
            # Check number of stops
            if flight.stops > Config.MAX_TRANSFERS:
                continue
            
            # Check layover durations
            for duration in flight.layover_durations:
                if duration < Config.MIN_LAYOVER_MINUTES:
                    logger.warning(f"Filtering flight with {duration}min layover (too short)")
                    is_acceptable = False
                    break
                elif duration > 6 * 60:  # More than 6 hours
                    logger.warning(f"Filtering flight with {duration}min layover (too long)")
                    is_acceptable = False
                    break
            
            if is_acceptable:
                filtered_flights.append(flight)
        
        return filtered_flights
    
    @staticmethod
    def rank_by_connection_quality(flights: List[FlightOffer]) -> List[FlightOffer]:
        """Rank flights by connection quality (fewer, better layovers first)"""
        def connection_score(flight):
            # Direct flights get priority
            if flight.stops == 0:
                return 1000
            
            # Fewer stops are better
            stops_penalty = flight.stops * 100
            
            # Layover quality matters
            layover_quality = LayoverOptimizer.evaluate_layover_quality(
                flight.layover_airports, flight.layover_durations
            )
            
            return 500 + (layover_quality * 200) - stops_penalty
        
        return sorted(flights, key=connection_score, reverse=True)

class PriceAnalyzer:
    """Analyze flight prices and identify deals"""
    
    def __init__(self, database=None):
        self.database = database
    
    def calculate_price_statistics(self, flights: List[FlightOffer]) -> Dict:
        """Calculate price statistics for a set of flights"""
        if not flights:
            return {}
        
        prices = [f.total_price for f in flights]
        
        stats = {
            'min_price': min(prices),
            'max_price': max(prices),
            'mean_price': np.mean(prices),
            'median_price': np.median(prices),
            'std_price': np.std(prices),
            'price_range': max(prices) - min(prices),
            'count': len(prices)
        }
        
        # Calculate quartiles
        stats['q25'] = np.percentile(prices, 25)
        stats['q75'] = np.percentile(prices, 75)
        
        return stats
    
    def identify_price_deals(self, flights: List[FlightOffer], 
                           historical_data: Optional[pd.DataFrame] = None) -> List[FlightOffer]:
        """Identify flights that are good deals based on current and historical pricing"""
        if not flights:
            return []
        
        # Current price analysis
        current_stats = self.calculate_price_statistics(flights)
        good_deals = []
        
        # Mark flights significantly below average as deals
        threshold = current_stats['mean_price'] - (current_stats['std_price'] * 0.5)
        
        for flight in flights:
            is_deal = False
            deal_reasons = []
            
            # Current pricing analysis
            if flight.total_price <= threshold:
                is_deal = True
                deal_reasons.append("Below average pricing")
            
            if flight.total_price <= current_stats['q25']:
                is_deal = True
                deal_reasons.append("Bottom 25% pricing")
            
            # Historical analysis (if available)
            if historical_data is not None and not historical_data.empty:
                try:
                    # Calculate Z-score vs historical prices
                    historical_mean = historical_data['price_usd'].mean()
                    historical_std = historical_data['price_usd'].std()
                    
                    if historical_std > 0:
                        z_score = (flight.total_price - historical_mean) / historical_std
                        if z_score <= -1.0:  # More than 1 std dev below mean
                            is_deal = True
                            deal_reasons.append(f"Historical Z-score: {z_score:.2f}")
                except Exception as e:
                    logger.warning(f"Historical analysis failed: {e}")
            
            if is_deal:
                # Add deal metadata to flight (would need to extend FlightOffer)
                flight.deal_reasons = deal_reasons
                good_deals.append(flight)
        
        return good_deals
    
    def calculate_convenience_score(self, flight: FlightOffer, max_price: float = None,
                                   max_duration: int = None) -> float:
        """
        Calculate convenience score based on price, duration, stops, and layovers
        Returns score from 0.0 (worst) to 1.0 (best)
        """
        # Normalize price (lower is better)
        if max_price and max_price > 0:
            price_score = 1.0 - (flight.total_price / max_price)
        else:
            price_score = 0.5  # Neutral if no reference
        
        # Normalize duration (shorter is better) 
        if max_duration and max_duration > 0:
            duration_score = 1.0 - (flight.duration_minutes / max_duration)
        else:
            duration_score = 0.5  # Neutral if no reference
        
        # Stops score (fewer is better)
        if flight.stops == 0:
            stops_score = 1.0
        elif flight.stops == 1:
            stops_score = 0.7
        elif flight.stops == 2:
            stops_score = 0.4
        else:
            stops_score = 0.1  # Too many stops
        
        # Layover quality score
        layover_score = LayoverOptimizer.evaluate_layover_quality(
            flight.layover_airports, flight.layover_durations
        )
        
        # Weighted combination
        convenience_score = (
            price_score * Config.WEIGHT_PRICE +
            duration_score * Config.WEIGHT_DURATION +
            stops_score * Config.WEIGHT_STOPS +
            layover_score * Config.WEIGHT_LAYOVER_QUALITY
        )
        
        return min(1.0, max(0.0, convenience_score))  # Clamp to [0, 1]

class FlightRanker:
    """Rank and select best flight options"""
    
    def __init__(self, price_analyzer: PriceAnalyzer):
        self.price_analyzer = price_analyzer
        self.layover_optimizer = LayoverOptimizer()
    
    def analyze_and_rank_flights(self, flights: List[FlightOffer], 
                                busy_dates: List[str] = None) -> FlightAnalysis:
        """
        Analyze flights and return primary choice + alternatives
        """
        if not flights:
            return FlightAnalysis(
                primary_option=None,
                alternatives=[],
                recommendations=["No flights found for the specified criteria"]
            )
        
        # Filter out problematic connections
        valid_flights = self.layover_optimizer.filter_problematic_connections(flights)
        
        if not valid_flights:
            return FlightAnalysis(
                primary_option=None,
                alternatives=[],
                recommendations=["All flights filtered due to poor connections"]
            )
        
        # Calculate statistics for scoring
        price_stats = self.price_analyzer.calculate_price_statistics(valid_flights)
        max_price = price_stats.get('max_price', 1000)
        max_duration = max((f.duration_minutes for f in valid_flights), default=600)
        
        # Calculate convenience scores
        for flight in valid_flights:
            flight.convenience_score = self.price_analyzer.calculate_convenience_score(
                flight, max_price, max_duration
            )
        
        # Sort by convenience score (highest first)
        ranked_flights = sorted(valid_flights, key=lambda f: f.convenience_score, reverse=True)
        
        # Select primary option (highest scoring)
        primary_option = ranked_flights[0]
        primary_option.is_primary_choice = True
        
        # Select alternatives (next best options, up to MAX_ALTERNATIVES - 1)
        alternatives = []
        for flight in ranked_flights[1:Config.MAX_ALTERNATIVES]:
            flight.is_alternative = True
            alternatives.append(flight)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            primary_option, alternatives, price_stats, busy_dates
        )
        
        return FlightAnalysis(
            primary_option=primary_option,
            alternatives=alternatives,
            price_statistics=price_stats,
            recommendations=recommendations
        )
    
    def find_flexible_date_alternatives(self, origin: str, destination: str, 
                                      preferred_date: str, busy_dates: List[str] = None,
                                      search_engine = None) -> Dict[str, FlightOffer]:
        """Find alternative flights on flexible dates"""
        if not search_engine:
            return {}
        
        flexible_options = search_engine.get_flexible_date_options(
            origin, destination, preferred_date, Config.FLEXIBLE_DAYS
        )
        
        # Filter out busy dates
        if busy_dates:
            for busy_date in busy_dates:
                flexible_options.pop(busy_date, None)
        
        # Rank options by convenience score for each date
        ranked_by_date = {}
        for date, flights in flexible_options.items():
            if flights:
                analysis = self.analyze_and_rank_flights(flights)
                if analysis.primary_option:
                    ranked_by_date[date] = analysis.primary_option
        
        return ranked_by_date
    
    def _generate_recommendations(self, primary: FlightOffer, alternatives: List[FlightOffer],
                                price_stats: Dict, busy_dates: List[str] = None) -> List[str]:
        """Generate human-readable recommendations"""
        recommendations = []
        
        # Primary option recommendation
        if primary.stops == 0:
            recommendations.append(f"✈️ Primary: Direct flight for ${primary.total_price:.0f} - Best convenience")
        else:
            recommendations.append(f"✈️ Primary: ${primary.total_price:.0f} with {primary.stops} stop(s) - Best overall value")
        
        # Price comparison
        if primary.total_price <= price_stats.get('q25', 0):
            recommendations.append("💰 Excellent deal - Price in bottom 25% of options")
        elif primary.total_price <= price_stats.get('median_price', 0):
            recommendations.append("👍 Good value - Below median price")
        
        # Duration insight
        duration_hours = primary.duration_minutes / 60
        if duration_hours <= 2:
            recommendations.append("⚡ Very fast - Under 2 hours total travel")
        elif duration_hours <= 4:
            recommendations.append("🚀 Quick trip - Under 4 hours total travel")
        
        # Alternative insights
        if alternatives:
            cheapest_alt = min(alternatives, key=lambda f: f.total_price)
            if cheapest_alt.total_price < primary.total_price * 0.95:
                savings = primary.total_price - cheapest_alt.total_price
                recommendations.append(f"💡 Alternative: Save ${savings:.0f} with similar convenience")
        
        # Layover warnings
        for flight in [primary] + alternatives[:2]:  # Check top options
            for i, duration in enumerate(flight.layover_durations):
                if duration < Config.MIN_LAYOVER_MINUTES:
                    airport = flight.layover_airports[i]
                    recommendations.append(f"⚠️ Warning: {duration}min layover in {airport} may be tight")
                elif duration > 4 * 60:  # Over 4 hours
                    airport = flight.layover_airports[i]
                    recommendations.append(f"🕐 Long layover: {duration//60}hr {duration%60}min in {airport}")
        
        # Schedule conflict advice
        if busy_dates:
            recommendations.append(f"📅 Note: {len(busy_dates)} dates marked as busy - showing alternatives")
        
        return recommendations
    
    def get_next_best_options(self, current_flights: List[FlightOffer], 
                             exclude_date: str) -> List[FlightOffer]:
        """Get next best options when primary choice date is unavailable"""
        # This would typically search for flights on alternative dates
        # For now, return the existing alternatives excluding the problematic date
        
        filtered_flights = []
        for flight in current_flights:
            # Check if flight's departure date matches the excluded date
            if hasattr(flight.segments[0], 'departure_datetime'):
                flight_date = flight.segments[0].departure_datetime.strftime('%Y-%m-%d')
                if flight_date != exclude_date:
                    filtered_flights.append(flight)
        
        # Re-analyze and rank the remaining options
        if filtered_flights:
            analysis = self.analyze_and_rank_flights(filtered_flights)
            return [analysis.primary_option] + analysis.alternatives
        
        return []

class NotificationManager:
    """Handle price alerts and notifications"""
    
    def __init__(self, database=None):
        self.database = database
    
    def check_price_drops(self, current_flights: List[FlightOffer], 
                         origin: str, destination: str) -> List[Dict]:
        """Check for significant price drops and create alerts"""
        if not self.database:
            return []
        
        # Get historical price data
        historical_data = self.database.get_price_history(origin, destination, days=30)
        
        if historical_data.empty:
            return []  # No historical data to compare
        
        alerts = []
        current_min_price = min(f.total_price for f in current_flights)
        historical_mean = historical_data['price_usd'].mean()
        historical_min = historical_data['price_usd'].min()
        
        # Check for significant drops
        drop_from_mean = historical_mean - current_min_price
        drop_pct_from_mean = (drop_from_mean / historical_mean) * 100
        
        if (drop_from_mean >= Config.PRICE_DROP_THRESHOLD_ABS or 
            drop_pct_from_mean >= Config.PRICE_DROP_THRESHOLD_PCT):
            
            alert = {
                'type': 'price_drop',
                'origin': origin,
                'destination': destination,
                'current_price': current_min_price,
                'historical_mean': historical_mean,
                'drop_amount': drop_from_mean,
                'drop_percent': drop_pct_from_mean,
                'message': f"Price drop alert: ${current_min_price:.0f} vs ${historical_mean:.0f} avg"
            }
            alerts.append(alert)
        
        # Check for historical lows
        if current_min_price <= historical_min * 1.05:  # Within 5% of historical low
            alert = {
                'type': 'historical_low',
                'origin': origin,
                'destination': destination,
                'current_price': current_min_price,
                'historical_low': historical_min,
                'message': f"Near historical low: ${current_min_price:.0f} (record: ${historical_min:.0f})"
            }
            alerts.append(alert)
        
        return alerts
    
    def should_send_notification(self, alert: Dict) -> bool:
        """Determine if notification should be sent based on alert significance"""
        if alert['type'] == 'price_drop':
            return (alert['drop_amount'] >= Config.PRICE_DROP_THRESHOLD_ABS or
                   alert['drop_percent'] >= Config.PRICE_DROP_THRESHOLD_PCT)
        elif alert['type'] == 'historical_low':
            return True
        
        return False