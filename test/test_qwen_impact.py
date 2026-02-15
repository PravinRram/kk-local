import os
import json
import sys
from datetime import datetime
from openai import OpenAI

def make_prompt(spec_rules: str, event_fields: dict) -> str:
    return (
        "You are the AI Impact Checker for Intergen Interaction. "
        "Follow the scoring rules and output format exactly. "
        "Only show max 4 reasons and max 4 setting changes. "
        "Use the provided event fields. "
        "\n\nSCORING RULES:\n" + spec_rules + 
        "\n\nEVENT FIELDS (JSON):\n" + json.dumps(event_fields, indent=2) +
        "\n\nOutput format:\n"
        "Overall: <Weak|OK|Strong> - <short label> (<score%>)\n\n"
        "Why it is <weak|ok|strong>:\n"
        "- <reason 1>\n"
        "- <reason 2>\n"
        "- <reason 3>\n"
        "- <reason 4>\n\n"
        "Change these settings:\n"
        "- <field> = <value> (<short explanation>)\n"
        "- <field> = <value> (<short explanation>)\n"
        "- <field> = <value> (<short explanation>)\n"
        "- <field> = <value> (<short explanation>)\n"
    )

def get_spec_rules() -> str:
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

6) Discoverability & matching (0–10)
public + tags → +10
public + no tags → +7 (reason: harder to match)
private + code + tags → +9
private + code + no tags → +6
private missing code → +2

Overall label:
Weak <60; OK 60–79; Strong >=80
Only include changes that improve score; max 4 reasons and max 4 changes.
"""

def build_sample_event() -> dict:
    return {
        "event_name": "Kampung Games Hour: Youth x Seniors",
        "start_date": "2026-01-10",
        "end_date": "2026-01-10",
        "start_time": "21:00",
        "end_time": "22:00",
        "location": "Community Hall, Level 2",
        "description": "Join us for casual games and bonding. Light activities and meet new friends.",
        "visibility": "public",
        "event_type": "physical",
        "image_source": "upload",
        "image_path": "uploads/sample.png",
        "ai_theme": None,
        "event_code": "KK-TEST",
        "interest_tags": "",
        "enable_group_chat": False,
        "enable_minigames": True,
    }

def main():
    # Use env var if available, otherwise use the provided key
    api_key = os.getenv("DASHSCOPE_API_KEY", "sk-58632e2d25ff49e4aeeaa1ddb8fad0f1")
    
    if not api_key:
        print("Missing DASHSCOPE_API_KEY environment variable.")
        sys.exit(1)

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
    except ImportError:
        print("openai module not found. Run: pip install openai")
        sys.exit(1)

    event_fields = build_sample_event()
    prompt = make_prompt(get_spec_rules(), event_fields)

    print("Calling Qwen-flash with sample event...")
    
    messages = [{"role": "user", "content": prompt}]
    
    try:
        completion = client.chat.completions.create(
            model="qwen-flash",
            messages=messages,
            extra_body={"enable_thinking": False},
            stream=True,
            max_tokens=2000
        )
        
        is_answering = False  # Indicates whether the response phase has started
        print("\n" + "=" * 20 + "Thinking process" + "=" * 20)
        
        for chunk in completion:
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                if not is_answering:
                    print(delta.reasoning_content, end="", flush=True)
            if hasattr(delta, "content") and delta.content:
                if not is_answering:
                    print("\n" + "=" * 20 + "Full response" + "=" * 20)
                    is_answering = True
                print(delta.content, end="", flush=True)
                
        print("\n")
        
    except Exception as e:
        print(f"Error calling API: {e}")

if __name__ == "__main__":
    main()
