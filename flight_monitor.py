import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json
import time
import logging
from typing import Dict, List, Optional

# Import our custom modules
from config import Config, DEFAULT_PREFERENCES
from database import FlightDatabase
from flight_api import FlightSearchEngine, FlightOffer
from price_analyzer import PriceAnalyzer, FlightRanker, NotificationManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration for mobile-friendly display
st.set_page_config(
    page_title="Cheap Flight Monitor",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Mobile-optimized dark theme CSS (based on your bond dashboard style)
st.markdown("""
<style>
    /* Main dark theme */
    .stApp {
        background-color: #0e1117;
        color: white;
    }
    
    /* Main header styling */
    .main-header {
        font-size: 2.5rem;
        color: #00d4aa;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: bold;
    }
    
    /* Section headers */
    .section-header {
        font-size: 1.5rem;
        color: #fafafa;
        margin: 1rem 0;
        padding: 0.5rem;
        background: linear-gradient(90deg, #1f2937, #374151);
        border-radius: 8px;
        border-left: 4px solid #00d4aa;
    }
    
    /* Flight card styling */
    .flight-card {
        background: #1f2937;
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #374151;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    .flight-card-primary {
        border-left: 4px solid #00d4aa;
        background: linear-gradient(135deg, #1f2937, #0f172a);
    }
    
    .flight-card-alternative {
        border-left: 4px solid #f59e0b;
    }
    
    /* Price styling */
    .price-primary {
        font-size: 2rem;
        font-weight: bold;
        color: #00d4aa;
    }
    
    .price-alternative {
        font-size: 1.8rem;
        font-weight: bold;
        color: #f59e0b;
    }
    
    /* Duration and stops styling */
    .flight-details {
        color: #9ca3af;
        font-size: 0.9rem;
        margin: 0.5rem 0;
    }
    
    /* Convenience score styling */
    .convenience-score {
        background: #374151;
        border-radius: 20px;
        padding: 0.3rem 0.8rem;
        color: #00d4aa;
        font-weight: bold;
        font-size: 0.8rem;
        display: inline-block;
    }
    
    /* Alert styling */
    .alert-box {
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        font-weight: bold;
    }
    
    .alert-deal {
        background-color: #059669;
        border: 1px solid #10b981;
        color: white;
    }
    
    .alert-warning {
        background-color: #d97706;
        border: 1px solid #f59e0b;
        color: white;
    }
    
    .alert-info {
        background-color: #1e40af;
        border: 1px solid #3b82f6;
        color: white;
    }
    
    /* Button styling */
    .book-button {
        background: linear-gradient(135deg, #00d4aa, #059669);
        color: white;
        padding: 0.8rem 1.5rem;
        border-radius: 8px;
        text-decoration: none;
        font-weight: bold;
        display: inline-block;
        text-align: center;
        border: none;
        cursor: pointer;
        font-size: 1rem;
        transition: all 0.3s ease;
    }
    
    .book-button:hover {
        background: linear-gradient(135deg, #059669, #047857);
        text-decoration: none;
        color: white;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #262730;
    }
    
    /* Main content area */
    .main .block-container {
        background-color: #0e1117;
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
        color: #ffffff;
    }
    
    /* Text colors */
    .stMarkdown, .stText, h1, h2, h3, p {
        color: #ffffff !important;
    }
    
    /* Metrics styling */
    .stMetric {
        background-color: #1f2937;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #374151;
    }
    
    /* Success/Error messages */
    .stSuccess {
        background-color: #1e4d3d;
        color: #ffffff;
    }
    
    .stError {
        background-color: #4d1e1e;
        color: #ffffff;
    }
    
    .stWarning {
        background-color: #4d3d1e;
        color: #ffffff;
    }
    
    .stInfo {
        background-color: #1e3d4d;
        color: #ffffff;
    }
    
    /* Mobile responsiveness */
    @media (max-width: 768px) {
        .main-header {
            font-size: 2rem;
        }
        .section-header {
            font-size: 1.2rem;
        }
        .price-primary {
            font-size: 1.5rem;
        }
        .price-alternative {
            font-size: 1.3rem;
        }
        .flight-card {
            padding: 0.8rem;
        }
    }
</style>
""", unsafe_allow_html=True)

class FlightMonitorApp:
    """Main application class for the Flight Monitor"""
    
    def __init__(self):
        self.db = FlightDatabase()
        self.search_engine = FlightSearchEngine()
        self.price_analyzer = PriceAnalyzer(self.db)
        self.flight_ranker = FlightRanker(self.price_analyzer)
        self.notification_manager = NotificationManager(self.db)
        
        # Initialize session state
        self._initialize_session_state()
    
    def _initialize_session_state(self):
        """Initialize Streamlit session state variables"""
        if 'user_preferences' not in st.session_state:
            # Try to load from database, otherwise use defaults
            prefs = self.db.get_user_preferences()
            st.session_state.user_preferences = prefs if prefs else DEFAULT_PREFERENCES.copy()
        
        if 'current_search_results' not in st.session_state:
            st.session_state.current_search_results = None
        
        if 'last_search_time' not in st.session_state:
            st.session_state.last_search_time = None
        
        if 'busy_dates' not in st.session_state:
            st.session_state.busy_dates = []
    
    def render_header(self):
        """Render the main application header"""
        st.markdown('<div class="main-header">✈️ Cheap Flight Monitor</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style='text-align: center; margin-bottom: 1.5rem; color: #9ca3af;'>
            <p>Find the best flights to Arizona & LA with smart alternatives for busy schedules</p>
        </div>
        """, unsafe_allow_html=True)
    
    def render_search_controls(self):
        """Render flight search controls"""
        st.markdown('<div class="section-header">🔍 Flight Search</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            departure_airport = st.selectbox(
                "From",
                options=["LAX", "SFO", "SEA", "DEN", "ORD", "JFK", "ATL", "DFW"],
                index=0,
                key="departure_airport"
            )
            
            departure_date = st.date_input(
                "Departure Date",
                value=datetime.now() + timedelta(days=14),
                min_value=datetime.now(),
                max_value=datetime.now() + timedelta(days=365),
                key="departure_date"
            )
        
        with col2:
            destination_airport = st.selectbox(
                "To",
                options=list(Config.get_all_destination_airports().keys()),
                format_func=lambda x: f"{x} - {Config.get_all_destination_airports()[x]}",
                key="destination_airport"
            )
            
            return_date = st.date_input(
                "Return Date (Optional)",
                value=None,
                min_value=departure_date,
                max_value=datetime.now() + timedelta(days=365),
                key="return_date"
            )
        
        # Search button
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            search_clicked = st.button("🔍 Search Flights", type="primary", key="search_button")
        with col2:
            auto_refresh = st.checkbox("Auto-refresh (5min)", key="auto_refresh")
        with col3:
            if st.session_state.last_search_time:
                st.write(f"Last: {st.session_state.last_search_time.strftime('%H:%M')}")
        
        return search_clicked, departure_airport, destination_airport, departure_date, return_date, auto_refresh
    
    def render_busy_dates_manager(self):
        """Render busy dates management interface"""
        with st.expander("📅 Manage Busy Dates", expanded=False):
            st.write("Mark dates when you're not available to travel:")
            
            # Add busy date
            col1, col2 = st.columns([3, 1])
            with col1:
                new_busy_date = st.date_input(
                    "Add busy date",
                    min_value=datetime.now(),
                    max_value=datetime.now() + timedelta(days=365),
                    key="new_busy_date"
                )
            with col2:
                if st.button("Add", key="add_busy_date"):
                    date_str = new_busy_date.strftime('%Y-%m-%d')
                    if date_str not in st.session_state.busy_dates:
                        st.session_state.busy_dates.append(date_str)
                        st.success(f"Added {date_str}")
                        st.rerun()
            
            # Display and manage existing busy dates
            if st.session_state.busy_dates:
                st.write("**Current busy dates:**")
                for i, date_str in enumerate(st.session_state.busy_dates):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"🚫 {date_str}")
                    with col2:
                        if st.button("Remove", key=f"remove_busy_{i}"):
                            st.session_state.busy_dates.remove(date_str)
                            st.rerun()
    
    def search_flights(self, origin: str, destination: str, departure_date: str, return_date: str = None):
        """Perform flight search and analysis"""
        with st.spinner("🔍 Searching for flights..."):
            # Search flights
            flights = self.search_engine.search_flights(
                origin, destination, departure_date, return_date
            )
            
            if not flights:
                st.error("No flights found for the specified criteria")
                return None
            
            # Analyze and rank flights
            analysis = self.flight_ranker.analyze_and_rank_flights(
                flights, st.session_state.busy_dates
            )
            
            # Store results
            st.session_state.current_search_results = analysis
            st.session_state.last_search_time = datetime.now()
            
            # Save to database
            search_id = self.db.save_flight_search(origin, destination, departure_date, return_date)
            if search_id:
                flight_data = []
                for flight in flights:
                    flight_dict = {
                        'airline_code': flight.segments[0].airline_code if flight.segments else '',
                        'airline_name': flight.segments[0].airline_name if flight.segments else '',
                        'flight_number': flight.segments[0].flight_number if flight.segments else '',
                        'origin': origin,
                        'destination': destination,
                        'departure_datetime': flight.segments[0].departure_datetime.isoformat() if flight.segments else '',
                        'arrival_datetime': flight.segments[-1].arrival_datetime.isoformat() if flight.segments else '',
                        'duration_minutes': flight.duration_minutes,
                        'stops': flight.stops,
                        'layover_airports': flight.layover_airports,
                        'layover_durations': flight.layover_durations,
                        'price_usd': flight.total_price,
                        'booking_url': flight.booking_url,
                        'convenience_score': flight.convenience_score
                    }
                    flight_data.append(flight_dict)
                
                self.db.save_flight_prices(search_id, flight_data)
            
            return analysis
    
    def render_flight_card(self, flight: FlightOffer, is_primary: bool = False):
        """Render a single flight option card"""
        card_class = "flight-card-primary" if is_primary else "flight-card-alternative"
        price_class = "price-primary" if is_primary else "price-alternative"
        
        # Calculate duration display
        hours = flight.duration_minutes // 60
        minutes = flight.duration_minutes % 60
        duration_str = f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        
        # Format departure and arrival times
        if flight.segments:
            dep_time = flight.segments[0].departure_datetime.strftime('%H:%M')
            arr_time = flight.segments[-1].arrival_datetime.strftime('%H:%M')
            airline_name = flight.segments[0].airline_name
        else:
            dep_time = arr_time = "TBD"
            airline_name = "Unknown"
        
        # Stops description
        if flight.stops == 0:
            stops_str = "Direct"
        elif flight.stops == 1:
            stops_str = f"1 stop in {flight.layover_airports[0]}"
        else:
            stops_str = f"{flight.stops} stops"
        
        # Convenience score display
        score_pct = int(flight.convenience_score * 100)
        
        card_html = f"""
        <div class="flight-card {card_class}">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="flex: 1;">
                    <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                        <span class="{price_class}">${flight.total_price:.0f}</span>
                        <span class="convenience-score" style="margin-left: 1rem;">
                            {score_pct}% match
                        </span>
                    </div>
                    <div class="flight-details">
                        <strong>{airline_name}</strong><br>
                        {dep_time} → {arr_time} ({duration_str})<br>
                        {stops_str}
                    </div>
                </div>
                <div style="margin-left: 1rem;">
                    <a href="{flight.booking_url}" target="_blank" class="book-button">
                        Book Now
                    </a>
                </div>
            </div>
        </div>
        """
        
        st.markdown(card_html, unsafe_allow_html=True)
    
    def render_flight_results(self, analysis):
        """Render flight search results"""
        if not analysis or not analysis.primary_option:
            st.warning("No suitable flights found")
            return
        
        # Display recommendations
        if analysis.recommendations:
            st.markdown('<div class="section-header">💡 Recommendations</div>', unsafe_allow_html=True)
            for rec in analysis.recommendations:
                if "deal" in rec.lower() or "excellent" in rec.lower():
                    st.markdown(f'<div class="alert-box alert-deal">{rec}</div>', unsafe_allow_html=True)
                elif "warning" in rec.lower():
                    st.markdown(f'<div class="alert-box alert-warning">{rec}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="alert-box alert-info">{rec}</div>', unsafe_allow_html=True)
        
        # Primary option
        st.markdown('<div class="section-header">🎯 Primary Choice</div>', unsafe_allow_html=True)
        self.render_flight_card(analysis.primary_option, is_primary=True)
        
        # Alternative options
        if analysis.alternatives:
            st.markdown('<div class="section-header">🔄 Alternative Options</div>', unsafe_allow_html=True)
            
            # Swipeable carousel effect with columns
            if len(analysis.alternatives) <= 2:
                cols = st.columns(len(analysis.alternatives))
                for i, flight in enumerate(analysis.alternatives):
                    with cols[i]:
                        self.render_flight_card(flight)
            else:
                # Use tabs for more than 2 alternatives (mobile-friendly)
                tab_names = [f"Option {i+1}" for i in range(len(analysis.alternatives))]
                tabs = st.tabs(tab_names)
                
                for i, flight in enumerate(analysis.alternatives):
                    with tabs[i]:
                        self.render_flight_card(flight)
    
    def render_price_history(self, origin: str, destination: str):
        """Render price history chart"""
        historical_data = self.db.get_price_history(origin, destination, days=30)
        
        if not historical_data.empty:
            st.markdown('<div class="section-header">📈 Price History (30 Days)</div>', unsafe_allow_html=True)
            
            fig = go.Figure()
            
            # Add price trend line
            fig.add_trace(go.Scatter(
                x=historical_data['recorded_at'],
                y=historical_data['price_usd'],
                mode='lines+markers',
                name='Price',
                line=dict(color='#00d4aa', width=2),
                marker=dict(size=6)
            ))
            
            # Customize layout for mobile
            fig.update_layout(
                title=f"Flight Prices: {origin} → {destination}",
                xaxis_title="Date",
                yaxis_title="Price (USD)",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                height=400,
                margin=dict(l=50, r=50, t=50, b=50),
                xaxis=dict(gridcolor='#374151'),
                yaxis=dict(gridcolor='#374151')
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    def render_flexible_dates(self, origin: str, destination: str, preferred_date: str):
        """Render flexible date options"""
        flexible_options = self.flight_ranker.find_flexible_date_alternatives(
            origin, destination, preferred_date, st.session_state.busy_dates, self.search_engine
        )
        
        if flexible_options:
            st.markdown('<div class="section-header">📅 Flexible Date Options</div>', unsafe_allow_html=True)
            
            # Create date comparison
            dates = list(flexible_options.keys())
            prices = [flexible_options[date].total_price for date in dates]
            
            # Sort by date
            date_price_pairs = sorted(zip(dates, prices))
            dates, prices = zip(*date_price_pairs)
            
            # Display as metrics
            cols = st.columns(min(len(dates), 4))  # Max 4 columns for mobile
            for i, (date, price) in enumerate(zip(dates, prices)):
                with cols[i % 4]:
                    # Calculate price difference from preferred date
                    preferred_flight = flexible_options.get(preferred_date)
                    if preferred_flight:
                        price_diff = price - preferred_flight.total_price
                        delta = f"{price_diff:+.0f}" if price_diff != 0 else "0"
                    else:
                        delta = None
                    
                    st.metric(
                        label=datetime.fromisoformat(date).strftime('%m/%d'),
                        value=f"${price:.0f}",
                        delta=delta
                    )
    
    def run(self):
        """Main application runner"""
        self.render_header()
        
        # Search controls
        search_clicked, origin, destination, dep_date, ret_date, auto_refresh = self.render_search_controls()
        
        # Busy dates management
        self.render_busy_dates_manager()
        
        # Perform search if requested
        if search_clicked:
            analysis = self.search_flights(
                origin, 
                destination, 
                dep_date.strftime('%Y-%m-%d'),
                ret_date.strftime('%Y-%m-%d') if ret_date else None
            )
            
            if analysis:
                st.success(f"Found {len([analysis.primary_option] + analysis.alternatives)} flight options")
        
        # Display results
        if st.session_state.current_search_results:
            self.render_flight_results(st.session_state.current_search_results)
            
            # Price history
            if st.checkbox("📈 Show Price History", key="show_history"):
                self.render_price_history(origin, destination)
            
            # Flexible dates
            if st.checkbox("📅 Show Flexible Dates", key="show_flexible"):
                self.render_flexible_dates(origin, destination, dep_date.strftime('%Y-%m-%d'))
        
        # Auto-refresh functionality
        if auto_refresh and st.session_state.current_search_results:
            time.sleep(Config.AUTO_REFRESH_SECONDS)
            st.rerun()
        
        # Footer
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; color: #6b7280; font-size: 0.8rem;'>
            📱 Optimized for mobile viewing | 🔄 Auto-refresh available<br>
            💡 Swipe and tap to navigate flight options
        </div>
        """, unsafe_allow_html=True)

def main():
    """Main entry point"""
    try:
        # Validate configuration
        missing_config = Config.validate_config()
        if missing_config:
            st.warning(f"Missing configuration: {', '.join(missing_config)}")
            st.info("Using demo mode with simulated flight data")
        
        # Run the application
        app = FlightMonitorApp()
        app.run()
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        st.error(f"An error occurred: {e}")
        st.info("Please refresh the page or contact support if the problem persists")

if __name__ == "__main__":
    main()