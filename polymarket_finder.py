import requests
import json
import time
import re
from datetime import datetime, timedelta, timezone

# Constants
API_BASE_URL = "https://gamma-api.polymarket.com"
MIN_PROB = 0.80
MAX_PROB = 0.95
RUN_DURATION_SEC = 600  # Run for 10 minutes
POLL_INTERVAL_SEC = 60  # Check every minute
MIN_VOLUME = 1000  # Minimum volume in dollars
MIN_DURATION_HOURS = 1  # Minimum time until market ends
MAX_DURATION_DAYS = 14  # Maximum time until market ends
CANDIDATE_LIMIT = 1000  # Number of top volume markets to fetch from API

# Categories to exclude (lowercase strings inside the list)
# Available categories include: "politics", "sports", "crypto", "finance", 
# "geopolitics", "tech", "culture", "pop-culture", "economy", "weather", "mentions", "elections"
# example["sports", "crypto", "mentions"]
EXCLUDED_CATEGORIES = ["sports"]   

# Sports specific exclusion logic (extra strict)
try:
    with open("sports_tags.txt", "r") as f:
        SPORTS_TAG_IDS = set(line.strip() for line in f if line.strip())
except FileNotFoundError:
    SPORTS_TAG_IDS = {"1", "2"} # 1 is usually Sports, 2 is often related

SPORTS_KEYWORDS = [
    "tournament", "masters", "championship", "match", " game", "league", 
    "nba", "nfl", "mlb", "nhl", "soccer", "football", "basketball", "tennis", 
    "golf", "cricket", "racing", "f1", "nascar", "ufc", "boxing", "olympics",
    "vs.", " vs ", "seed", "bracket", "score", "draw", "points", "spread", "over/under",
    "fc ", " fc", "club de futbol", "real madrid", "barcelona", "liverpool", "manchester",
    "fifa", "uefa", "ncaa", "world cup", "super bowl", "grand slam", "ball", "rookie",
    "final four", "march madness", "atp ", "wta ", "ufc ", "pga ", "liv golf", "lol ", "esports", "blast ",
    "o/u ", "over/under", "handicap", "total games", "total maps", "series winner"
]

def get_markets():
    """Fetch markers and also specifically look for user-mentioned topics."""
    markets_map = {}
    
    # 1. Top volume markets
    params = {
        "limit": CANDIDATE_LIMIT,
        "active": "true",
        "closed": "false",
        "order": "volume",
        "ascending": "false"
    }
    try:
        r = requests.get(f"{API_BASE_URL}/markets", params=params)
        if r.status_code == 200:
            for m in r.json():
                if m.get("id"): markets_map[m["id"]] = m
    except: pass
    
    # 2. Specific keyword searches to ensure we find target examples (Larry Page, edgeX, etc.)
    for kw in ["edgeX", "Larry Page", "richest", "token launch", "Anthropic", "Apple", "BTC"]:
        try:
            r = requests.get(f"{API_BASE_URL}/markets", params={"limit": 100, "active": "true", "query": kw})
            if r.status_code == 200:
                for m in r.json():
                    if m.get("id"): markets_map[m["id"]] = m
        except: pass
        
    return list(markets_map.values())

def extract_date_from_text(text):
    """Try to extract a date from title/question text if endDate is null or invalid."""
    if not text:
        return None
    # Look for patterns like "March 31, 2026" or "3/31/26"
    months_regex = "(January|February|March|April|May|June|July|August|September|October|November|December)"
    # Pattern 1: Month Day, Year
    match = re.search(f"{months_regex}\\s+(\\d+),?\\s*(20\\d{{2}})?", text, re.IGNORECASE)
    if match:
        month_name = match.group(1).lower()
        day = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else 2026
        
        m_map = {"january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
                 "july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
        try:
            return datetime(year, m_map[month_name], day, tzinfo=timezone.utc)
        except:
            return None
    return None

def get_best_market_date(market):
    """Determine the actual expiration date of a market."""
    d_str = market.get("endDate") or market.get("end_date")
    if d_str:
        try:
            d = datetime.fromisoformat(d_str.replace("Z", "+00:00"))
            if 2024 < d.year < 2100:
                return d
        except: pass
    
    # Fallback to title parsing
    text = market.get("question") or market.get("title") or ""
    return extract_date_from_text(text)

def filter_markets(markets):
    """Apply filters: 80-95% probability, no sports, and duration strictly 1h to 2m."""
    filtered = []
    now = datetime.now(timezone.utc)
    min_end_date = now + timedelta(hours=MIN_DURATION_HOURS)
    max_end_date = now + timedelta(days=MAX_DURATION_DAYS)
    
    for market in markets:
        # Exclusion 0: Volume < MIN_VOLUME
        volume = float(market.get("volume") or 0)
        if volume < MIN_VOLUME:
            continue

        # Exclusion 1: Excluded Categories
        category = (market.get("category") or "").lower()
        if any(c == category or c in category.split('-') for c in EXCLUDED_CATEGORIES):
            continue

        # Exclusion 2: Excluded Tags
        tags = market.get("tags", [])
        tag_labels = [str(tag.get("label")).lower() for tag in tags]
        if any(c in label for label in tag_labels for c in EXCLUDED_CATEGORIES):
            continue

        # Exclusion 3: Strict Sports Exclusion (If "sports" is in EXCLUDED_CATEGORIES)
        if "sports" in EXCLUDED_CATEGORIES:
            if any(str(tag.get("id")) in SPORTS_TAG_IDS for tag in tags):
                continue

            full_title = (market.get("question") or market.get("title") or "").lower()
            if any(kw in full_title for kw in SPORTS_KEYWORDS):
                # Whitelist specific non-sports categories to avoid over-filtering
                if category not in ["politics", "crypto", "business", "tech", "science", "economy"]:
                    continue

        # Filter 1: Duration strictly 1 hour to 2 months
        end_date = get_best_market_date(market)
        if not end_date:
            continue
            
        if not (min_end_date <= end_date <= max_end_date):
            continue

        # Filter 2: Probability (80-95%)
        prices_str = market.get("outcomePrices")
        if not prices_str:
            continue
            
        try:
            prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            probs = [float(p) for p in prices]
            
            outcomes_raw = market.get("outcomes")
            outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else (outcomes_raw or [])
            
            found_outcomes = []
            for idx, p in enumerate(probs):
                if MIN_PROB <= p <= MAX_PROB:
                    label = outcomes[idx] if idx < len(outcomes) else f"Outcome {idx}"
                    found_outcomes.append({"label": label, "prob": p})
            
            if not found_outcomes:
                continue
                
            market["_found_outcomes"] = found_outcomes
            market["_actual_end_date"] = end_date
        except:
            continue

        filtered.append(market)
        
    return filtered

def main():
    print("🚀 Polymarket High-Probability Market Finder (Non-Sports)")
    print(f"Filtering: {MIN_PROB*100}% - {MAX_PROB*100}% probability")
    print(f"Timeframe: STRICTLY ending in {MIN_DURATION_HOURS}h to {MAX_DURATION_DAYS}d from today")
    print("-" * 50)
    
    start_time = time.time()
    seen_ids = set()
    market_count = 0
    
    while time.time() - start_time < RUN_DURATION_SEC:
        now = datetime.now(timezone.utc)
        
        raw_markets = get_markets()
        filtered = filter_markets(raw_markets)
        
        # requested logic: if too many results (>20), change timeframe to 1 day+
        if len(filtered) > 20:
            one_day_later = now + timedelta(days=1)
            filtered = [m for m in filtered if m["_actual_end_date"] >= one_day_later]

        for market in filtered:
            m_id = market.get("id")
            if m_id not in seen_ids:
                seen_ids.add(m_id)
                
                # Title Logic: If it's a grouped market, show both parent and sub-title
                event_title = market.get("title") # Usually the parent event title
                market_question = market.get("question") # Specific question
                sub_title = market.get("groupItemTitle")
                
                display_title = market_question
                if event_title and event_title != market_question:
                    display_title = f"{event_title} -> {market_question}"
                elif sub_title:
                    display_title = f"{market_question} ({sub_title})"
                
                found_outcomes = market.get("_found_outcomes", [])
                
                # URL Logic: Find the correct event page (parent event)
                # 1. Try events list (usually index 0 is the parent event)
                slug = None
                events = market.get("events", [])
                if isinstance(events, list) and len(events) > 0:
                    # Filter out the market's own slug if possible, or just take the first
                    # Usually the parent event has a different slug
                    for e in events:
                        e_slug = e.get("slug")
                        if e_slug and e_slug != market.get("slug"):
                            slug = e_slug
                            break
                    if not slug:
                        slug = events[0].get("slug")
                
                # 2. Try eventSlug field
                if not slug:
                    slug = market.get("eventSlug")
                
                # 3. Fallback to market slug
                if not slug:
                    slug = market.get("slug")
                
                url = f"https://polymarket.com/event/{slug}"
                
                market_count += 1
                print(f"✅ [{market_count}] Found Market: {display_title}")
                print(f"   Market ID: {m_id}")
                print(f"   End Date: {market['_actual_end_date'].strftime('%Y-%m-%d')}")
                for out in found_outcomes:
                    print(f"   Target Outcome: {out['label']} ({out['prob']*100:.1f}%)")
                print(f"   Link: {url}")
                print("-" * 30)
        
        if len(seen_ids) == 0:
            print("Searching for matches...")
            
        time.sleep(POLL_INTERVAL_SEC)

    print("\n✅ Search complete.")
    print(f"Total unique markets found: {len(seen_ids)}")

if __name__ == "__main__":
    main()
