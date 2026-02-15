import os
import json
import traceback
import random
from datetime import datetime, date, timedelta, time
from flask import url_for
from EventDBHelper import DatabaseHelper
from keybert import KeyBERT
from AIAgentHelper import AIAgentHelper
from duckduckgo_search import DDGS

# Initialize database
project_root = os.path.dirname(__file__)
db_helper = DatabaseHelper(db_name=os.path.join(project_root, "events.db"))

# Initialize AI Agent Helper
ai_agent = AIAgentHelper()

# Initialize KeyBERT once
kw_model = KeyBERT()

# Define standard seed keywords for consistency
SEED_KEYWORDS = [
    # Removed age-based keywords
    "sports", "fitness", "health", "wellness",
    "food", "cooking", "dining",
    "arts", "crafts", "music", "dance", "culture",
    "games", "gaming", "technology", "digital",
    "nature", "outdoor", "gardening",
    "education", "learning", "workshop",
    "volunteering", "community", "social"
]

# Words to explicitly block
BLOCKED_KEYWORDS = {"seniors", "youth", "youths", "children", "family", "intergenerational", "ages", "age"}

def parse_date_filters(date_filter):
    today = date.today()
    if date_filter == "today":
        start = today
        end = today
    elif date_filter == "week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif date_filter == "month":
        start = today.replace(day=1)
        if start.month == 12:
            next_month_start = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_month_start = start.replace(month=start.month + 1, day=1)
        end = next_month_start - timedelta(days=1)
    else:
        start = None
        end = None
    return start, end

# Helper - Calculates end datetime based on start time and duration
def compute_end_time(start_time_str, duration_min):
    if not start_time_str or not duration_min:
        return None
    hh, mm = map(int, start_time_str.split(":"))
    start_dt = datetime.combine(date.today(), time(hour=hh, minute=mm))
    end_dt = start_dt + timedelta(minutes=int(duration_min))
    return end_dt.strftime("%H:%M")

# Helper - Formats date string to 'Day, DD Mon YYYY'
def format_date(dstr):
    try:
        dt = datetime.strptime(dstr, "%Y-%m-%d")
        return dt.strftime("%a, %d %b %Y")
    except Exception:
        return dstr

def format_date_range(start_d, end_d):
    if start_d and end_d:
        return f"{format_date(start_d)} - {format_date(end_d)}"
    elif start_d:
        return format_date(start_d)
    return ""

# Helper - Formats 24h time string to 12h format with AM/PM
def format_time_12hr(time_str):
    if not time_str:
        return ""
    try:
        t = datetime.strptime(time_str, "%H:%M")
        return t.strftime("%I:%M %p").lstrip("0").lower()
    except Exception:
        return time_str

def format_date_simple(date_str):
    if not date_str:
        return ""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%d %b %Y")
    except Exception:
        return date_str

# Helper - Generates the appropriate URL for an image based on its source (upload/ai)
def build_image_url(image_source, image_path):
    if not image_path:
        return None
    if image_source == "upload":
        return url_for("events.media_file", filename=image_path)
    if image_source == "ai":
        if image_path.startswith("http://") or image_path.startswith("https://"):
            return image_path
        return url_for("events.media_file", filename=image_path)
    return None

def _update_user_interest_weights(user_id, event_id, delta=1):
    # Get event tags
    event = db_helper.get_event_by_id(event_id)
    if not event:
        return
        
    conn = db_helper._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT interest_tags FROM events WHERE event_id = ?", (event_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row or not row[0]:
        return
        
    tags_str = row[0]
    tags = [t.strip().lower() for t in tags_str.split(",") if t.strip()]
    
    # Get current interests
    raw_interests = db_helper.get_user_interests(user_id)
    interests_dict = {}
    if raw_interests:
        try:
            interests_dict = json.loads(raw_interests)
        except json.JSONDecodeError:
            interests_dict = {tag.strip().lower(): 1 for tag in raw_interests.split(",") if tag.strip()}
            
    # Update counts
    for tag in tags:
        current = interests_dict.get(tag, 0)
        new_val = current + delta
        if new_val <= 0:
            if tag in interests_dict:
                del interests_dict[tag]
        else:
            interests_dict[tag] = new_val
        
    # Save back
    db_helper.update_user_interests(user_id, json.dumps(interests_dict))

# Helper to parse interests
def _get_user_interests_dict(user_id):
    raw = db_helper.get_user_interests(user_id)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback for CSV format
        return {tag.strip().lower(): 1 for tag in raw.split(",") if tag.strip()}

# Helper for weighted interest matching
def calculate_match_score(interests_dict, description, tags_str):
    score = 0
    desc_lower = description.lower() if description else ""
    
    # Check against description (weight 1)
    for interest, weight in interests_dict.items():
        if interest in desc_lower:
            score += weight
    
    # Check against tags (weight 2)
    if tags_str:
        event_tags = [t.strip().lower() for t in tags_str.split(",")]
        for tag in event_tags:
            if tag in interests_dict:
                # Double weight for direct tag match
                score += interests_dict[tag] * 2
    return score
