# Polymarket Custom Market Finder

A script to find and track high-probability outcomes on Polymarket.

## Features
- Filters outcomes based on user-defined probability.
- Excludes sports-related markets using category tags and keywords.
- **Strict Volume Filter**: Excludes markets with less than $500 total volume.
- Timeframe filter: Configurable window for market end dates (e.g., 1h to 60d).
- Real-time monitoring with periodic polling.
- Intelligent URL generation for event pages.
- Sequential numbering for found markets.

## Usage
1. Ensure you have the `requests` library installed: `pip install requests`.
2. Run the script: `python polymarket_finder.py`.
3. The script will poll for new qualifying markets every minute for 10 minutes.

## Configuration
You can adjust the following constants in `polymarket_finder.py`:
- `MIN_PROB`: Lower bound for probability (default: 0.80).
- `MAX_PROB`: Upper bound for probability (default: 0.95).
- `MIN_VOLUME`: Minimum volume threshold (default: 500).
- `MIN_DURATION_HOURS`: Minimum hours until market end (default: 1).
- `MAX_DURATION_DAYS`: Maximum days until market end (default: 60).
- `CANDIDATE_LIMIT`: Number of top volume markets to fetch from the API (default: 1000).
- `EXCLUDED_CATEGORIES`: List of categories to filter out (e.g., `["sports", "crypto", "mentions"]`). Available UI categories include:
  - `politics`, `sports`, `crypto`, `finance`, `geopolitics`, `tech`
  - `culture`, `pop-culture`, `economy`, `weather`, `mentions`, `elections`
- `RUN_DURATION_SEC`: Total runtime (default: 600s).
- `POLL_INTERVAL_SEC`: Frequency of checking for new markets (default: 60s).
