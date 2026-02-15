import os
import json
from openai import OpenAI
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure OpenAI client for Qwen
API_KEY = os.getenv("DASHSCOPE_API_KEY")
client = None

if API_KEY:
    try:
        client = OpenAI(
            api_key=API_KEY,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")

def get_spec_rules() -> str:
    """
    Returns the scoring rules for the AI Impact Checker.
    Updated to remove 'interest_tags' from the rules.
    """
    return """
1) Timing accessibility (0–25)
If start_time between 10:00–18:00 → +25
If between 18:01–20:30 → +18
Else → +8
Penalty: If start_time >= 21:00 add reason “Too late for many seniors.”

2) Duration comfort (0–15)
Compute duration in minutes across dates and times.
60–120 → +15
30–59 or 121–180 → +10
<30 or >180 → +5
Reasons: Too short (“Too short to build connection.”) / Too long (“Too long; seniors may get tired.”)

3) Type-location consistency (0–10)
online + location contains any of [hall, level, blk, community, cc, room] → mismatch
physical + location contains any of [zoom, google meet, meet.google, teams, webinar] → mismatch
consistent → +10; mismatch → +3 + add reason + suggest change

4) Feature support (0–20)
both ON → +20
chat ON only → +14
minigames ON only → +10 (reason: no support channel)
both OFF → +4 (reason: low interaction scaffolding)
Extra: if event_type == online and enable_group_chat == false → add reason “Online events need chat for warm-up + support.”

5) Description clarity (0–20)
length >= 80 → +8 else +3
contains any of [share, story, game, karaoke, chat, learn] → +6
contains any of [agenda, duration, minutes, hour, we will, schedule] → +6
If score < 12 add reason + suggest improving description

6) Discoverability (0–10)
public → +10
private + code → +9
private missing code → +2

Overall label:
Weak <60; OK 60–79; Strong >=80
Only include changes that improve score; max 4 reasons and max 4 changes.
"""

def analyze_event_impact(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyzes the event data using Qwen and returns a structured impact report.
    """
    if not client:
        print("AIHelper: OpenAI client not initialized.")
        return None

    prompt = f"""
    You are the AI Impact Checker for Intergen Interaction.
    Follow the scoring rules and output format exactly.
    Only show max 4 reasons and max 4 setting changes.
    Use the provided event fields.

    IMPORTANT INSTRUCTIONS FOR "CHANGES":
    1. If suggesting a time duration change:
       - Do NOT output "end_time".
       - Instead, output "duration_minutes" (integer).
       - Example: {{"field": "duration_minutes", "value": 90, "explanation": "Extend to 90 mins"}}
    
    2. If suggesting a description change:
       - Do NOT rewrite the entire description.
       - Output ONLY the new text segment to be added (e.g., the missing agenda).
       - The system will prepend this to the user's existing description.
       - Example: {{"field": "description", "value": "Agenda: 15min Icebreaker...", "explanation": "Add agenda"}}

    SCORING RULES:
    {get_spec_rules()}

    EVENT FIELDS (JSON):
    {json.dumps(event_data, indent=2)}

    Output strictly valid JSON with this structure:
    {{
      "score": <number 0-100>,
      "label": "<Weak|OK|Strong>",
      "short_label": "<short phrase like 'feels like a one off event'>",
      "reasons": ["<reason 1>", "<reason 2>", ...],
      "changes": [
        {{
          "field": "<field_name>",
          "value": <new_value>,
          "explanation": "<short explanation>"
        }},
        ...
      ]
    }}
    Do not include markdown formatting (like ```json). Just the raw JSON string.
    """

    try:
        completion = client.chat.completions.create(
            model="qwen-flash",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            extra_body={"enable_thinking": False}, # Disable thinking for clean JSON output
            stream=False
        )
        
        text = completion.choices[0].message.content.strip()
        
        # Clean up any potential markdown backticks if the model ignores the instruction
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
            
        if text.endswith("```"):
            text = text[:-3]
        
        result = json.loads(text)
        
        # Format the changes so the app can easily apply them
        # Convert changes to a dictionary where field is the key and value is the new value
        simple_changes = {item["field"]: item["value"] for item in result.get("changes", [])}
        result["changes_json"] = json.dumps(simple_changes)
        
        return result
    except Exception as e:
        print(f"AI Analysis Error: {e}")
        return None
