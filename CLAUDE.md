# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Cheap Flight Monitor** built with Streamlit that tracks flight prices to Arizona (PHX) and Los Angeles (LAX) with intelligent alternative options and layover optimization. The application is mobile-optimized for frequent smartphone checking.

## Architecture & Structure

### Core Components
- **flight_monitor.py**: Main Streamlit application with mobile-optimized interface
- **flight_api.py**: API integration layer for flight data fetching
- **price_analyzer.py**: Price analysis, ranking algorithms, and alert logic
- **database.py**: SQLite database management for price history
- **config.py**: Configuration settings and API keys

### Key Classes
- `FlightSearchEngine`: Core flight search with alternative options
- `PriceAnalyzer`: Price tracking, Z-score analysis, and ranking algorithms
- `LayoverOptimizer`: Minimize connection times and transfer counts
- `FlightMonitor`: Main orchestration class

### Data Sources & APIs
- **Primary**: Amadeus Flight API (requires API key)
- **Secondary**: RapidAPI flight services
- **Fallback**: Web scraping capabilities (Google Flights, Kayak)

## Development Commands

### Running the Application
```bash
streamlit run flight_monitor.py
```

### Environment Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Database Initialization
The SQLite database will be created automatically on first run.

## Key Features & Functionality

### Smart Flight Search
1. **Primary Recommendation**: Cheapest available flight
2. **Alternative Options**: Next 3-5 cheapest flights for schedule flexibility
3. **Flexible Dates**: ±3 days price comparison from optimal date
4. **Schedule Conflict Resolution**: Mark unavailable dates, get next best options

### Layover & Transfer Optimization
- **Connection Time Minimization**: Avoid short (<90min) and long (>4hr) layovers
- **Transfer Count Priority**: Direct > 1-stop > 2-stop (never 3+ transfers)
- **Airport Quality Scoring**: Consider layover airport convenience
- **Route Intelligence**: Multi-airport support (PHX/TUS for AZ, LAX/BUR/LGB/SNA for LA)

### Mobile Interface Features
- **Flight Options Carousel**: Swipe through top 5 alternatives
- **Quick Decision Cards**: Price, duration, stops at a glance
- **Schedule Integration**: Calendar interface for marking busy dates  
- **One-Tap Booking**: Direct airline booking page redirects

### Smart Ranking Algorithm
Weighted scoring system:
- Price (40%)
- Total travel time (30%)
- Number of stops (20%)  
- Layover quality (10%)

## Configuration Notes

### API Keys Required
- Amadeus API key for flight data
- Optional: Email service for notifications
- Optional: SMS service for mobile alerts

### Mobile Optimization
- Dark theme optimized for smartphone viewing
- Touch-friendly interface with swipe navigation
- Responsive design with minimal data usage
- Auto-refresh capabilities with user control

### Price Tracking & Alerts
- Historical price storage in SQLite
- Z-score analysis for identifying deals
- Customizable price thresholds
- Email/SMS notifications for price drops

## Performance Considerations
- Session state caching for API rate limiting
- Intelligent refresh intervals (user-configurable)
- Database indexing for quick price history queries
- Fallback mechanisms when primary APIs fail

## User Workflow
1. **App Launch**: See today's top 5 flight options
2. **Swipe Navigation**: Browse alternative flights
3. **Calendar Marking**: Mark unavailable dates
4. **Pull Refresh**: Update prices on demand
5. **Tap Booking**: Redirect to airline for purchase

## Multi-Destination Support
### Arizona Options
- PHX (Phoenix Sky Harbor) - Primary
- TUS (Tucson International) - Alternative
- FLG (Flagstaff Pulliam) - Regional option

### Los Angeles Area Options  
- LAX (Los Angeles International) - Primary
- BUR (Hollywood Burbank) - Alternative
- LGB (Long Beach) - Alternative
- SNA (John Wayne Orange County) - Alternative

## Technical Architecture
- **Frontend**: Streamlit with custom CSS for mobile optimization
- **Backend**: Python with async API calls
- **Database**: SQLite for price history and user preferences
- **APIs**: Amadeus primary, RapidAPI secondary, web scraping fallback
- **Notifications**: Email/SMS integration for price alerts